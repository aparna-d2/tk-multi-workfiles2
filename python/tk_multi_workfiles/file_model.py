# Copyright (c) 2014 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


import sgtk
from sgtk.platform.qt import QtGui, QtCore
from sgtk import TankError

from .find_files import FileFinder

class FileModel(QtGui.QStandardItemModel):
    """
    """
    # signals
    search_started = QtCore.Signal(object)
    files_found = QtCore.Signal(object)
    search_failed = QtCore.Signal(object, object)
    
    _BASE_ROLE = QtCore.Qt.UserRole + 32
    GROUP_NODE_ROLE = _BASE_ROLE + 1
    FILE_ITEM_ROLE = _BASE_ROLE + 2
    SEARCH_STATUS_ROLE = _BASE_ROLE + 3
    SEARCH_MSG_ROLE = _BASE_ROLE + 4

    NODE_TYPE_ROLE = _BASE_ROLE + 5
    (FILE_NODE_TYPE, GROUP_NODE_TYPE, FOLDER_NODE_TYPE) = range(3)
    
    (SEARCHING, SEARCH_COMPLETED, SEARCH_FAILED) = range(3)
    
    class _BaseItem(QtGui.QStandardItem):
        """
        """
        def __init__(self, typ, text=None):
            """
            """
            QtGui.QStandardItem.__init__(self, text)
            self._type = typ
            
        def data(self, role=QtCore.Qt.UserRole+1):
            """
            """
            if role == FileModel.NODE_TYPE_ROLE:
                return self._type
            else:
                # just return the default implementation:
                return QtGui.QStandardItem.data(self, role)
    
        def setData(self, value, role=QtCore.Qt.UserRole+1):
            """
            """
            if role == FileModel.NODE_TYPE_ROLE:
                # do nothing as the data can't be set:
                pass
            else:
                # call the base implementation:
                QtGui.QStandardItem.setData(self, value, role) 
    
    class _FileItem(_BaseItem):
        """
        """
        def __init__(self, file_item):
            """
            """
            FileModel._BaseItem.__init__(self, typ=FileModel.FILE_NODE_TYPE)
            self._file_item = file_item
            
        @property
        def file_item(self):
            return self._file_item
    
        def data(self, role=QtCore.Qt.UserRole+1):
            """
            """
            if role == QtCore.Qt.DisplayRole:
                return "%s, v%0d" % (self._file_item.name, self._file_item.version)
            elif role == FileModel.FILE_ITEM_ROLE:
                return self._file_item
            else:
                # just return the default implementation:
                return FileModel._BaseItem.data(self, role)
    
        def setData(self, value, role=QtCore.Qt.UserRole+1):
            """
            """
            if role == QtCore.Qt.DisplayRole:
                # do nothing as it can't be set!
                pass
            elif role == FileModel.FILE_ITEM_ROLE:
                self._file_item = value
                self.emitDataChanged()
            else:
                # call the base implementation:
                FileModel._BaseItem.setData(self, value, role) 
    
    class _FolderItem(_BaseItem):
        """
        """
        def __init__(self, name, entity):
            FileModel._BaseItem.__init__(self, typ=FileModel.FOLDER_NODE_TYPE, text=name)
            self._entity = entity
            
        
    
    class _GroupItem(_BaseItem):
        """
        """
        def __init__(self, name):
            FileModel._BaseItem.__init__(self, typ=FileModel.GROUP_NODE_TYPE, text=name)
            
            self._search_status = FileModel.SEARCHING
            self._search_msg = ""    
    
        def set_search_status(self, status, msg=None):
            self._search_status = status
            self._search_msg = msg
            self.emitDataChanged()

        def data(self, role=QtCore.Qt.UserRole+1):
            """
            """
            if role == FileModel.SEARCH_STATUS_ROLE:
                return self._search_status
            elif role == FileModel.SEARCH_MSG_ROLE:
                return self._search_msg
            elif role == FileModel.GROUP_NODE_ROLE:
                # always return true!
                return True
            else:
                # just return the default implementation:
                return FileModel._BaseItem.data(self, role)
    
        def setData(self, value, role=QtCore.Qt.UserRole+1):
            """
            """
            if role == FileModel.SEARCH_STATUS_ROLE:
                self._search_status = value
                self.emitDataChanged()
            elif role == FileModel.SEARCH_MSG_ROLE:
                self._search_msg = value
                self.emitDataChanged()
            elif role == FileModel.GROUP_NODE_ROLE:
                # can't be set!
                pass
            else:
                # call the base implementation:
                FileModel._BaseItem.setData(self, value, role) 
    
    
    def __init__(self, sg_data_retriever, parent=None):
        """
        """
        QtGui.QStandardItemModel.__init__(self, parent)
        
        # sg data retriever is used to download thumbnails in the background
        self._sg_data_retriever = sg_data_retriever
        if self._sg_data_retriever:
            self._sg_data_retriever.work_completed.connect(self._on_data_retriever_work_completed)
            self._sg_data_retriever.work_failure.connect(self._on_data_retriever_work_failed)
            
        self._pending_thumbnail_requests = {}
        
        # we'll need a file finder to be able to find files:
        self._finder = FileFinder()
        self._finder.files_found.connect(self._on_finder_files_found)
        self._finder.search_failed.connect(self._on_finder_search_failed)
        
        self._in_progress_searches = {}
        
        self._cache_dirty = True
        self._file_item_cache = {}
        
    class _CacheInfo(object):
        def __init__(self):
            self.versions = {}
            self.items = {}
            self.environment = None
        
    def get_file_versions(self, key):
        """
        """
        # return the cached versions
        cache_info = self._file_item_cache.get(key) 
        return cache_info.versions if cache_info else {}

    def get_file_info(self, key):
        """
        """
        cache_info = self._file_item_cache.get(key)
        if not cache_info:
            return None
        return (cache_info.versions, cache_info.environment)
        
    def refresh_files(self, search_details):
        """
        Asynchronously refresh the list of files in the model based on the
        supplied filters and context.
        """
        # stop all previous searches:
        search_ids = self._in_progress_searches.keys()
        self._in_progress_searches = {}
        for id in search_ids:
            self._finder.stop_search(id)
    
        # clear existing data from model:
        self.clear()
        self._file_item_cache = {}
        
        for search in search_details:
            # add a 'group' item to the model:
            new_item = FileModel._GroupItem(search.name)
            new_item.set_search_status(FileModel.SEARCHING)
            self.invisibleRootItem().appendRow(new_item)
            new_index = new_item.index()
            
            # start a search for this new group:
            search_id = self._finder.begin_search(search)
            self._in_progress_searches[search_id] = new_item
            
            # emit signal that we have started a new search for this index:
            self.search_started.emit(new_index)
            
            # and add folder items for any children:
            for child in search.child_entities:
                child_name = child.get("name", "Entity")
                child_entity = child.get("entity")
                
                # add a folder item to the model:
                folder_item = FileModel._FolderItem(child_name, child_entity)
                folder_item.setIcon(QtGui.QIcon(":/tk-multi-workfiles/folder_512x400.png"))
                new_item.appendRow(folder_item)
        
    def _on_data_retriever_work_completed(self, uid, request_type, data):
        """
        """
        if not uid in self._pending_thumbnail_requests:
            return
        item = self._pending_thumbnail_requests[uid]
        del(self._pending_thumbnail_requests[uid])
        
        thumb_path = data.get("thumb_path")
        if not thumb_path:
            return
        
        # create a QPixMap for the path:
        thumb_pm = QtGui.QPixmap(thumb_path)
        
        # update the thumbnail on the file for this item:
        file = item.file_item
        file.thumbnail = thumb_pm
        item.emitDataChanged()
    
        # finally, see of there are any work file versions of this file that don't have a
        # thumbnail that could make use of this thumbnail:
        cache_info = self._file_item_cache.get(file.key)
        if not cache_info:
            return
        
        for v, file_version in sorted(cache_info.versions.iteritems(), reverse=True):
            if (v > file_version.version 
                or file_version.is_published 
                or (not file_version.is_local)
                or file_version.thumbnail_path
                or file_version.thumbnail):
                continue

            # we can use the thumbnail for this version of the work file - yay!             
            file_version.thumbnail = thumb_pm
            cache_info.items[v].emitDataChanged()
            

    
    def _on_data_retriever_work_failed(self, uid, error_msg):
        """
        """
        if uid in self._pending_thumbnail_requests:
            del(self._pending_thumbnail_requests[uid])
        #print "Failed to find thumbnail for id %s: %s" % (uid, error_msg)        
        
    def _on_finder_files_found(self, search_id, file_list, environment):
        """
        Called when the finder has found some files.
        """
        if search_id not in self._in_progress_searches:
            # ignore result
            return
        parent_model_item = self._in_progress_searches[search_id]
        del(self._in_progress_searches[search_id])

        # add files to model:
        new_rows = []
        for file in file_list:
            # create a new model item for this file:
            new_item = FileModel._FileItem(file)
            new_rows.append(new_item)

            # if this is from a published file then we want to retrieve the thumbnail
            # if one is available:                        
            if file.is_published and file.thumbnail_path and not file.thumbnail:
                # request the thumbnail using the data retriever:
                request_id = self._sg_data_retriever.request_thumbnail(file.thumbnail_path, 
                                                                       "PublishedFile", 
                                                                       file.published_file_id,
                                                                       "image")
                self._pending_thumbnail_requests[request_id] = new_item

            # add info to the cache indexed by the file key:
            info = self._file_item_cache.setdefault(file.key, FileModel._CacheInfo())
            info.versions[file.version] = file
            info.items[file.version] = new_item
            info.environment = environment

        if new_rows:
            # we have new rows so lets add them to the model:
            parent_model_item.appendRows(new_rows)
            
        # update the parent group item to indicate that the search has been completed:
        if isinstance(parent_model_item, FileModel._GroupItem):
            parent_model_item.set_search_status(FileModel.SEARCH_COMPLETED)
            
        # emit signal indicating that the search has been completed:
        self.files_found.emit(parent_model_item.index())
    
    def _on_finder_search_failed(self, search_id, error):
        """
        Called when the finder search fails for some reason!
        """
        if search_id not in self._in_progress_searches:
            # ignore result
            return
        parent_model_item = self._in_progress_searches[search_id]
        del(self._in_progress_searches[search_id])
        
        #print "SEARCH %d FAILED: %s" % (search_id, error)
        
        if isinstance(parent_model_item, FileModel._GroupItem):
            parent_model_item.set_search_status(FileModel.SEARCH_FAILED, error)
        
        # emit signal:
        self.search_failed.emit(parent_model_item.index(), error)



