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
Multi Work Files 2.  
Provides File Open/Save functionality for Work Files
"""
import sgtk

class MultiWorkFiles(sgtk.platform.Application):

    def init_app(self):
        """
        Called as the application is being initialized
        """
        self._tk_multi_workfiles = self.import_module("tk_multi_workfiles")

        application_has_scenes = True
        if self.engine.name == "tk-mari":
            # Mari doesn't have the concept of a current scene so this app shouldn't
            # provide any commands!
            application_has_scenes = False

        # register commands:
        if application_has_scenes:
            self.engine.register_command("File Open...", self.show_file_open_dlg, {"short_name":"file_open"})
            self.engine.register_command("File Save...", self.show_file_save_dlg, {"short_name":"file_save"})

        #self.engine.register_command("Run crash test", self.run_crash_test, {"short_name":"run_crash_test"})

        # Process auto startup options - but only on certain supported platforms
        # because of the way QT inits and connects to different host applications
        # differently, in conjunction with the 'boot' process in different tools,
        # the behaviour can be very different.  

        # currently, we have done basic QA on nuke and maya so we limit these options to 
        # those two engines for now. 
        SUPPORTED_ENGINES = ["tk-nuke", "tk-maya", "tk-3dsmax"]

        if self.engine.has_ui and not hasattr(sgtk, "_tk_multi_workfiles2_launch_at_startup"):

            # this is the very first time we have run this application
            sgtk._tk_multi_workfiles2_launch_at_startup = True

            if self.get_setting('launch_at_startup'):
                # show the file manager UI
                if self.engine.name in SUPPORTED_ENGINES:
                    # use a single-shot timer to show the open dialog to allow everything to
                    # finish being set up first:
                    from sgtk.platform.qt import QtCore
                    QtCore.QTimer.singleShot(200, self.show_file_open_dlg)
                else:
                    self.log_warning("Sorry, the launch at startup option is currently not supported "
                                     "in this engine! You can currently only use it with the following "
                                     "engines: %s" % ", ".join(SUPPORTED_ENGINES))

    def destroy_app(self):
        """
        Clean up app
        """
        self.log_debug("Destroying tk-multi-workfiles2")
        
    def show_file_open_dlg(self):
        """
        Launch the main File Open UI
        """
        self._tk_multi_workfiles.WorkFiles.show_file_open_dlg()

    def show_file_save_dlg(self):
        """
        Launch the main File Save UI
        """
        self._tk_multi_workfiles.WorkFiles.show_file_save_dlg()

    def run_crash_test(self):
        self._tk_multi_workfiles.WorkFiles.run_crash_test()

    @property
    def shotgun(self):
        """
        Subclassing of the shotgun property on the app base class. 
        This is a temporary arrangement to be able to time some of the shotgun calls. 
        """
        # get the real shotgun from the application base class
        app_shotgun = sgtk.platform.Application.shotgun.fget(self)
        # return a wrapper back which produces debug logging
        return DebugWrapperShotgun(app_shotgun, self.log_debug)
        
        
class DebugWrapperShotgun(object):
    
    def __init__(self, sg_instance, log_fn):
        self._sg = sg_instance
        self._log_fn = log_fn
        self.config = sg_instance.config
        
    def find(self, *args, **kwargs):
        self._log_fn("SG API find start: %s %s" % (args, kwargs))
        data = self._sg.find(*args, **kwargs)
        self._log_fn("SG API find end")
        return data

    def find_one(self, *args, **kwargs):
        self._log_fn("SG API find_one start: %s %s" % (args, kwargs))
        data = self._sg.find_one(*args, **kwargs)
        self._log_fn("SG API find_one end")
        return data

    def create(self, *args, **kwargs):
        self._log_fn("SG API create start: %s %s" % (args, kwargs))
        data = self._sg.create(*args, **kwargs)
        self._log_fn("SG API create end")
        return data

    def update(self, *args, **kwargs):
        self._log_fn("SG API update start: %s %s" % (args, kwargs))
        data = self._sg.update(*args, **kwargs)
        self._log_fn("SG API update end")
        return data

    def insert(self, *args, **kwargs):
        self._log_fn("SG API insert start: %s %s" % (args, kwargs))
        data = self._sg.insert(*args, **kwargs)
        self._log_fn("SG API insert end")
        return data
    
