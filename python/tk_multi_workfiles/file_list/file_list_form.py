# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
"""

import sgtk
from sgtk.platform.qt import QtCore, QtGui

views = sgtk.platform.import_framework("tk-framework-qtwidgets", "views")
spinner_widget = sgtk.platform.import_framework("tk-framework-qtwidgets", "spinner_widget")
SpinnerWidget = spinner_widget.SpinnerWidget

GroupedListView = views.GroupedListView

from ..file_model import FileModel
from ..ui.file_list_form import Ui_FileListForm
from ..ui.file_group_widget import Ui_FileGroupWidget

from .file_tile import FileTile
from .group_header_widget import GroupHeaderWidget
from .file_proxy_model import FileProxyModel


class FileGroupWidget(views.GroupWidgetBase):
    """
    """
    def __init__(self, parent=None):
        """
        Construction
        """
        views.GroupWidgetBase.__init__(self, parent)
        
        # set up the UI
        self._ui = Ui_FileGroupWidget()
        self._ui.setupUi(self)
        
        self._ui.expand_check_box.stateChanged.connect(self._on_expand_checkbox_state_changed)
        
        # replace the spinner widget with our SpinnerWidget widget:
        proxy_widget = self._ui.spinner
        proxy_size = proxy_widget.geometry()
        proxy_min_size = proxy_widget.minimumSize()
        
        spinner_widget = SpinnerWidget(self)
        spinner_widget.setMinimumSize(proxy_min_size)
        spinner_widget.setGeometry(proxy_size)        

        layout = self._ui.horizontalLayout
        idx = layout.indexOf(proxy_widget)
        layout.removeWidget(proxy_widget)
        layout.insertWidget(idx, spinner_widget)
        
        self._ui.spinner.setParent(None)
        self._ui.spinner.deleteLater()
        self._ui.spinner = spinner_widget
        
        self._show_msg = False

    def set_item(self, model_idx):
        """
        """
        label = model_idx.data()
        self._ui.expand_check_box.setText(label)
        
        # update if the spinner should be visible or not:
        search_status = model_idx.data(FileModel.SEARCH_STATUS_ROLE)
        if search_status == None:
            search_status = FileModel.SEARCH_COMPLETED
            
        # show the spinner if needed:
        self._ui.spinner.setVisible(search_status == FileModel.SEARCHING)
        
        search_msg = ""
        if search_status == FileModel.SEARCHING:
            search_msg = "Searching for files..."
        elif search_status == FileModel.SEARCH_COMPLETED:
            if not model_idx.model().hasChildren(model_idx):
                search_msg = "No files found!"
        elif search_status == FileModel.SEARCH_FAILED:
            search_msg = model_idx.data(FileModel.SEARCH_MSG_ROLE) or ""
        self._ui.msg_label.setText(search_msg)
                        
        self._show_msg = bool(search_msg)
                        
        show_msg = self._show_msg and self._ui.expand_check_box.checkState() == QtCore.Qt.Checked
        self._ui.msg_label.setVisible(show_msg)

    def set_expanded(self, expand=True):
        """
        """
        if (self._ui.expand_check_box.checkState() == QtCore.Qt.Checked) != expand:
            self._ui.expand_check_box.setCheckState(QtCore.Qt.Checked if expand else QtCore.Qt.Unchecked)

    def _on_expand_checkbox_state_changed(self, state):
        """
        """
        show_msg = self._show_msg and state == QtCore.Qt.Checked
        self._ui.msg_label.setVisible(show_msg)
        
        self.toggle_expanded.emit(state != QtCore.Qt.Unchecked)
    

class TestItemDelegate(views.GroupedListViewItemDelegate):

    def __init__(self, view):
        views.GroupedListViewItemDelegate.__init__(self, view)
        
        self._item_widget = None

    def create_group_widget(self, parent):
        return FileGroupWidget(parent)

    def _get_painter_widget(self, model_index, parent):
        """
        """
        if not model_index.isValid():
            return None
        if not self._item_widget:
            self._item_widget = FileTile(parent)
        return self._item_widget

    def _on_before_paint(self, widget, model_index, style_options):
        """
        """
        if not isinstance(widget, FileTile):
            # this class only paints FileTile widgets
            return
        
        label = ""
        icon = None
        is_publish = False
        is_editable = True
        not_editable_reason = None
        
        file_item = model_index.data(FileModel.FILE_ITEM_ROLE)
        if file_item:
            # build label:
            label = "<b>%s, v%03d</b>" % (file_item.name, file_item.version)
            if file_item.is_published:
                label += "<br>%s" % file_item.format_published_by_details()
            elif file_item.is_local:
                label += "<br>%s" % file_item.format_modified_by_details()

            # retrieve the icon:                
            icon = file_item.thumbnail
            is_publish = file_item.is_published
            is_editable = file_item.editable
            not_editable_reason = file_item.not_editable_reason
        else:
            label = model_index.data()
            icon = model_index.data(QtCore.Qt.DecorationRole)

        # update widget:
        widget.title = label
        widget.set_thumbnail(icon)
        widget.selected = (style_options.state & QtGui.QStyle.State_Selected) == QtGui.QStyle.State_Selected
        widget.set_is_publish(is_publish)
        widget.set_is_editable(is_editable, not_editable_reason)

    def sizeHint(self, style_options, model_index):
        """
        """
        if not model_index.isValid():
            return QtCore.QSize()
        
        if model_index.parent() != self.view.rootIndex():
            return self._get_painter_widget(model_index, self.view).size()
        else:
            # call base class:
            return views.GroupedListViewItemDelegate.sizeHint(self, style_options, model_index)

class FileListForm(QtGui.QWidget):
    """
    """
    
    file_selected = QtCore.Signal(object)
    file_double_clicked = QtCore.Signal(object)
    file_context_menu_requested = QtCore.Signal(object, object)
    
    def __init__(self, search_label, show_work_files=True, show_publishes=False, show_all_versions=False, parent=None):
        """
        Construction
        """
        QtGui.QWidget.__init__(self, parent)
        
        self._show_work_files = show_work_files
        self._show_publishes = show_publishes
        self._filter_model = None
        
        # set up the UI
        self._ui = Ui_FileListForm()
        self._ui.setupUi(self)
        
        self._ui.search_ctrl.set_placeholder_text("Search %s" % search_label)
        self._ui.search_ctrl.search_edited.connect(self._on_search_changed)
        
        self._ui.details_radio_btn.setEnabled(False) # (AD) - temp
        self._ui.details_radio_btn.toggled.connect(self._on_view_toggled)

        self._ui.all_versions_cb.setChecked(show_all_versions)
        self._ui.all_versions_cb.toggled.connect(self._on_show_all_versions_toggled)
        
        self._ui.file_list_view.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self._ui.file_list_view.doubleClicked.connect(self._on_file_double_clicked)
        
        self._ui.file_list_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._ui.file_list_view.customContextMenuRequested.connect(self._on_context_menu_requested)
        
        item_delegate = TestItemDelegate(self._ui.file_list_view)
        self._ui.file_list_view.setItemDelegate(item_delegate)

    def _on_context_menu_requested(self, pnt):
        """
        """
        # get the item under the point:
        idx = self._ui.file_list_view.indexAt(pnt)
        if not idx or not idx.isValid():
            return
        
        # get the file from the index:
        file = idx.data(FileModel.FILE_ITEM_ROLE)
        if not file:
            return

        # remap the point from the source widget:
        pnt = self.sender().mapTo(self, pnt)
        
        # emit a more specific signal:
        self.file_context_menu_requested.emit(file, pnt)

    @property
    def selected_file(self):
        """
        """
        selection_model = self._ui.file_list_view.selectionModel()
        if not selection_model:
            return None
        
        selected_indexes = selection_model.selectedIndexes()
        if len(selected_indexes) != 1:
            return False
                
        file = selected_indexes[0].data(FileModel.FILE_ITEM_ROLE)

        return file

    def set_model(self, model):
        """
        """
        show_all_versions = self._ui.all_versions_cb.isChecked()
        
        # create a filter model around the source model:
        self._filter_model = FileProxyModel(show_work_files=self._show_work_files, 
                                            show_publishes=self._show_publishes,
                                            show_all_versions = show_all_versions,
                                            parent=self)
        self._filter_model.setSourceModel(model)

        # set automatic sorting on the model:
        self._filter_model.sort(0, QtCore.Qt.DescendingOrder)
        self._filter_model.setDynamicSortFilter(True)

        # connect the views to the filtered model:        
        self._ui.file_list_view.setModel(self._filter_model)
        self._ui.file_details_view.setModel(self._filter_model)
        
        # connect to the selection model:
        selection_model = self._ui.file_list_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
        
    def _on_search_changed(self, search_text):
        """
        """
        # update the proxy filter search text:
        filter_reg_exp = QtCore.QRegExp(search_text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString)
        self._filter_model.setFilterRegExp(filter_reg_exp)
                
    def _on_view_toggled(self, checked):
        """
        """
        if self._ui.details_radio_btn.isChecked():
            self._ui.view_pages.setCurrentWidget(self._ui.details_page)
        else:
            self._ui.view_pages.setCurrentWidget(self._ui.list_page)
            
    def _on_show_all_versions_toggled(self, checked):
        """
        """
        self._filter_model.show_all_versions = checked
        
    def _on_file_double_clicked(self, idx):
        """
        """
        # map the index to the source model and emit signal:
        idx = self._filter_model.mapToSource(idx)
        self.file_double_clicked.emit(idx)
        
    def _on_selection_changed(self, selected, deselected):
        """
        """
        selected_index = None
        
        selected_indexes = selected.indexes()
        if len(selected_indexes) == 1:
            # extract the selected model index from the selection:
            selected_index = self._filter_model.mapToSource(selected_indexes[0])
            
        # emit selection_changed signal:            
        self.file_selected.emit(selected_index)        
        
        
        
        