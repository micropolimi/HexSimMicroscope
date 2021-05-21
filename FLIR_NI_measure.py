# -*- coding: utf-8 -*-
"""
Created on Fri May 7 11:43:27 2021

@authors: Andrea Bassi. Politecnico di Milano
"""
from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from ScopeFoundry import h5_io
import pyqtgraph as pg
import numpy as np
import os, time
#from PyQt5.QtWidgets import QTableWidgetItem
from qtpy.QtWidgets import QTableWidgetItem


class FlirNImeasure(Measurement):
    
    name = "FLIR_NI_measurement"
    
    def setup(self):
        """
        Runs once during App initialization.
        This is the place to load a user interface file,
        define settings, and set up data structures.
        For Pointgrey Grasshopper CMOS the pixelsize is: 5.86um
        """
        
        self.ui_filename = sibling_path(__file__, "hexSIM.ui")
        self.ui = load_qt_ui_file(self.ui_filename)    
        self.settings.New('measure', dtype=bool, initial=False)         
        self.settings.New('save_h5', dtype=bool, initial=False)         
        self.settings.New('refresh_period',dtype = float, unit ='s', spinbox_decimals = 3, initial = 0.05, vmin = 0)        
        
        self.settings.New('magnification', dtype=float, initial=63, spinbox_decimals= 2)  
        self.settings.New('pixel_size', dtype=float, initial=5.86, spinbox_decimals= 2)  
        
        #self.settings.New('xsampling', dtype=float, unit='um', initial=0.093, spinbox_decimals= 4) 
        #self.settings.New('ysampling', dtype=float, unit='um', initial=0.093, spinbox_decimals= 4)
        #self.settings.New('zsampling', dtype=float, unit='um', initial=1.0)
        
        self.auto_range = self.settings.New('auto_range', dtype=bool, initial=True)
        self.settings.New('auto_levels', dtype=bool, initial=True)
        self.settings.New('level_min', dtype=int, initial=60)
        self.settings.New('level_max', dtype=int, initial=4000)
        
        self.settings.New('delay', dtype=float, initial = 0.0 , unit = 's')
        
        
        self.image_gen = self.app.hardware['FLIRhw']
        
        self.settings.New('num_phases', dtype=int, initial=7, vmin = 1)
        self.settings.New('num_channels', dtype=int, initial=2, vmin = 1)
        self.settings.num_phases.hardware_set_func = self.resize_UItable
        self.settings.num_channels.hardware_set_func = self.resize_UItable
        self.add_operation('write_table', self.write_UItable)
        self.add_operation('clear_table', self.clear_UItable)
        
        self.ni_ao_0 = self.app.hardware['Analog_Output_0']
        self.ni_ao_1 = self.app.hardware['Analog_Output_1']
        
        self.setup_UItable()
                
    def setup_figure(self):
        """
        Runs once during App initialization, after setup()
        This is the place to make all graphical interface initializations,
        build plots, etc.
        """
        
        # connect ui widgets to measurement/hardware settings or functions
        self.ui.start_pushButton.clicked.connect(self.start)
        self.ui.interrupt_pushButton.clicked.connect(self.interrupt)
        self.settings.measure.connect_to_widget(self.ui.measure_checkBox)
        self.settings.auto_levels.connect_to_widget(self.ui.autoLevels_checkbox)
        self.auto_range.connect_to_widget(self.ui.autoRange_checkbox)
        self.settings.level_min.connect_to_widget(self.ui.min_doubleSpinBox) 
        self.settings.level_max.connect_to_widget(self.ui.max_doubleSpinBox) 
        self.settings.num_phases.connect_to_widget(self.ui.phases_doubleSpinBox) 
        self.settings.num_channels.connect_to_widget(self.ui.channels_doubleSpinBox) 
        
        # Set up pyqtgraph graph_layout in the UI
        self.imv = pg.ImageView()
        self.ui.image_groupBox.layout().addWidget(self.imv)
        colors = [(0, 0, 0),
                  (45, 5, 61),
                  (84, 42, 55),
                  (150, 87, 60),
                  (208, 171, 141),
                  (255, 255, 255)
                  ]
        cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)
        self.imv.setColorMap(cmap)
        
        
    def update_display(self):
        """
        Displays (plots) the numpy array self.buffer. 
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        """
        self.display_update_period = self.settings['refresh_period'] 
       
        if  self.settings['measure']:        
            length = self.image_gen.frame_num.val
            self.settings['progress'] = (self.frame_index +1) * 100/length
        
        if hasattr(self, 'img'):
            self.imv.setImage(self.img.T,
                                autoLevels = self.settings['auto_levels'],
                                autoRange = self.auto_range.val,
                                levelMode = 'mono'
                                )
            
            if self.settings['auto_levels']:
                lmin,lmax = self.imv.getHistogramWidget().getLevels()
                self.settings['level_min'] = lmin
                self.settings['level_max'] = lmax
            else:
                self.imv.setLevels( min= self.settings['level_min'],
                                    max= self.settings['level_max'])
            
    
    def measure(self):
        self.image_gen.settings['acquisition_mode'] = 'MultiFrame'
        self.settings['save_h5'] = True
        self.image_gen.settings['frame_num'] = self.settings['num_phases']
                
        voltages = self.read_from_UItable()
        first_frame_acquired = False
        frame_num  = self.image_gen.frame_num.val
        
        self.image_gen.camera.set_framenum(1) # acquire 1 frame at a time
        self.image_gen.camera.acq_start()
        
        for frame_idx in range(frame_num):
            
            v0 = float(voltages[0][frame_idx])
            v1 = float(voltages[1][frame_idx])
            self.ni_ao_0.AO_device.write_constant_voltage(v0)
            self.ni_ao_1.AO_device.write_constant_voltage(v1)
            time.sleep(0.05) #TODO remove after solving nissue
            self.frame_index = frame_idx
            self.image_gen.camera.acq_start()
            self.img = self.image_gen.camera.get_nparray()
            self.image_gen.camera.acq_stop()                
            if self.settings['save_h5']:
                if not first_frame_acquired:
                    self.create_h5_file()
                    first_frame_acquired = True
                    
                self.image_h5[frame_idx,:,:] = self.img
                self.h5file.flush()
            
            if self.interrupt_measurement_called:
                break
            time.sleep(self.settings['delay'])
        self.image_gen.camera.acq_stop()
    
    
    
    
    
    
    def run(self):
        self.image_gen.read_from_hardware()
        
        try:          
            self.frame_index = 0          
            """
            If measure is not active, acquire frames indefinitely. No save in h5 is performed 
            """
            self.image_gen.settings['acquisition_mode'] = 'Continuous'
            self.image_gen.camera.acq_start() 
            while not self.interrupt_measurement_called:
                 
                self.img = self.image_gen.camera.get_nparray()
                if self.interrupt_measurement_called:
                    break
                if self.settings['measure']:
                    """
                    If measure is activated, acquisition is interrupted a measurement is run
                    """
                    self.image_gen.camera.acq_stop()
                    self.measure()
                    break
        finally:            
            
            self.image_gen.camera.acq_stop()
            if self.settings['save_h5'] and hasattr(self, 'h5file'):
                # make sure to close the data file
                self.h5file.close() 
                self.settings['save_h5'] = False
                
            self.ni_ao_0.stop()
            self.ni_ao_1.stop()                       
    
    
    def setup_UItable(self):
        cols = self.settings.num_phases.val
        rows = self.settings.num_channels.val
        self.set_UItable_row_col(rows, cols)
        for j in range(cols):    
            for i in range(rows):
                self.settings.New(f'table{i,j}', dtype=float, initial=0.0)
                
    
    def resize_UItable(self,*args):
        cols = self.settings.num_phases.val
        rows = self.settings.num_channels.val
        self.set_UItable_row_col(rows, cols)
        for j in range(cols):    
            for i in range(rows):
                if not hasattr(self.settings, f'table{i,j}'):
                    self.settings.New(f'table{i,j}', dtype=float, initial=0.0)
    
    def set_UItable_row_col(self, rows=2, cols=7):
        """ 
        Changes the ui table to a specified number of rows and columns

        """
        amplitude_table = self.ui.tableWidget
        amplitude_table.setColumnCount(cols)
        amplitude_table.setRowCount(rows)
    
    def read_from_UItable(self):
        """
        get the values from the ui table and write them into the settings 
        """
        table = self.ui.tableWidget
        rows = table.rowCount()
        cols = table.columnCount()
        values = [[0.0] * cols for i in range(rows)]
        for j in range(cols):
            for i in range(rows):
              if table.item(i,j) is not None:
                  # print(table.item(i,j).text())
                  values[i][j]  = table.item(i,j).text()  
              if hasattr(self.settings, f'table{i,j}'):
                  self.settings[f'table{i,j}'] = values[i][j] 
        # print(values)
        return values  


    def write_UItable(self):
        """
        write the values into the table from the settings
        """
        table = self.ui.tableWidget
        rows = table.rowCount()
        cols = table.columnCount()
        for j in range(cols): 
            for i in range(rows):
                  # print(table.item(i,j).text())
                  if hasattr(self.settings, f'table{i,j}'):
                      val = self.settings[f'table{i,j}']
                      table.setItem(i,j, QTableWidgetItem(str(val)))
            
    def clear_UItable(self):
        """
        sets all the values of the table to 0
        
        """
        table = self.ui.tableWidget
        table.clearContents()
        
    def create_saving_directory(self):
        
        if not os.path.isdir(self.app.settings['save_dir']):
            os.makedirs(self.app.settings['save_dir'])
         
    def create_h5_file(self):                   
        self.create_saving_directory()
        # file name creation
        timestamp = time.strftime("%y%m%d_%H%M%S", time.localtime())
        sample = self.app.settings['sample']
        #sample_name = f'{timestamp}_{self.name}_{sample}.h5'
        if sample == '':
            sample_name = '_'.join([timestamp, self.name])
        else:
            sample_name = '_'.join([timestamp, sample, self.name])
        fname = os.path.join(self.app.settings['save_dir'], sample_name + '.h5')
        
        self.h5file = h5_io.h5_base_file(app=self.app, measurement=self, fname = fname)
        self.h5_group = h5_io.h5_create_measurement_group(measurement=self, h5group=self.h5file)
        
        img_size = self.img.shape
        dtype=self.img.dtype
        
        length = self.image_gen.frame_num.val
        self.image_h5 = self.h5_group.create_dataset(name  = 't0/c0/image', 
                                                  shape = [length, img_size[0], img_size[1]],
                                                  dtype = dtype)
        
        xy_sampling = self.settings['pixel_size'] / self.settings['magnification']
        self.image_h5.attrs['element_size_um'] =  [1.0,xy_sampling,xy_sampling]
                   

    