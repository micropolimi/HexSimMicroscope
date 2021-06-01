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
from HexSimProcessor.SIM_processing.hexSimProcessor import HexSimProcessor

class FlirNImeasure(Measurement):
    
    name = "FLIR_NI_measurement"
    
    def setup(self):
        """
        Runs once during App initialization.
        This is the place to load a user interface file,
        define settings, and set up data structures.
        """
        
        self.ui_filename = sibling_path(__file__, "hexSIMcalibration.ui")
        self.ui = load_qt_ui_file(self.ui_filename)    
        self.settings.New('iterations', dtype=int, initial=1, vmin=0) 
        
        self.settings.New('magnification', dtype=float, initial=63, spinbox_decimals= 2)  
        self.settings.New('pixelsize', dtype=float, initial=5.86, spinbox_decimals= 2, unit='um') #For Pointgrey Grasshopper CMOS the pixelsize is: 5.86um 
        self.settings.New('n', dtype=float, initial=1.000, spinbox_decimals= 3)  
        self.settings.New('NA', dtype=float, initial=0.75, spinbox_decimals= 3) 
        self.settings.New('wavelength', dtype=float, initial=0.532, spinbox_decimals= 3, unit='um')  
        
        self.settings.New('alpha', dtype=float, initial=0.500,  spinbox_decimals=3)
        self.settings.New('beta', dtype=float, initial=0.950,  spinbox_decimals=3)
        self.settings.New('w', dtype=float, initial=5.00, spinbox_decimals=2)
        self.settings.New('eta', dtype=float, initial=0.70, spinbox_decimals=2)
        self.settings.New('find_carrier', dtype=bool, initial=True)
        self.settings.New('gpu', dtype=bool, initial=False) 
        self.settings.New('selectROI', dtype=bool, initial=False) 
        self.settings.New('roiX', dtype=int, initial=600)
        self.settings.New('roiY', dtype=int, initial=1200)
        self.settings.New('ROI_size', dtype=int, initial=512, vmin=1, vmax=2048) 
        
        self.auto_range = self.settings.New('auto_range', dtype=bool, initial=True)
        self.settings.New('auto_levels', dtype=bool, initial=True)
        self.settings.New('level_min', dtype=int, initial=60)
        self.settings.New('level_max', dtype=int, initial=4000)
        
        self.settings.New('calibrate', dtype=bool, initial=False) 
        self.settings.New('measure', dtype=bool, initial=False)         
        self.settings.New('save_h5', dtype=bool, initial=False)         
        self.settings.New('refresh_period',dtype = float, unit ='s', spinbox_decimals = 3, initial = 0.05, vmin = 0)        
        
        self.settings.New('num_phases', dtype=int, initial=7, vmin = 1)
        self.settings.New('num_channels', dtype=int, initial=2, vmin = 1)
        self.settings.num_phases.hardware_set_func = self.resize_UItable
        self.settings.num_channels.hardware_set_func = self.resize_UItable
        self.add_operation('write_table', self.write_UItable)
        self.add_operation('clear_table', self.clear_UItable)
        
        
        self.image_gen = self.app.hardware['FLIRhw']
       
        self.settings.New('delay', dtype=float, initial = 0.0 , unit = 's')
        
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
        self.settings.calibrate.connect_to_widget(self.ui.calibrate_checkBox)
        self.settings.auto_levels.connect_to_widget(self.ui.autoLevels_checkbox)
        self.auto_range.connect_to_widget(self.ui.autoRange_checkbox)
        self.settings.level_min.connect_to_widget(self.ui.min_doubleSpinBox) 
        self.settings.level_max.connect_to_widget(self.ui.max_doubleSpinBox) 
        self.settings.num_phases.connect_to_widget(self.ui.phases_doubleSpinBox) 
        self.settings.num_channels.connect_to_widget(self.ui.channels_doubleSpinBox) 
        
        # Set up pyqtgraph graph_layout in the UI
        self.imv = pg.ImageView()
        self.imv.ui.menuBtn.hide()
        self.imv.ui.roiBtn.hide()
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
            self.imv.setImage(self.img,
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
        if hasattr(self, 'roi'):         
            x,y = self.roi.pos()
            s = self.settings['ROI_size']//2
            self.settings['roiX'] = x + s
            self.settings['roiY'] = y + s
               
    
    def measure(self,save_data):
        self.image_gen.settings['acquisition_mode'] = 'MultiFrame'
        self.settings['save_h5'] = save_data
        ph = self.image_gen.settings['frame_num'] = self.settings['num_phases']
                
        voltages = self.read_from_UItable()
        first_frame_acquired = False
        frame_num  = self.image_gen.frame_num.val
        
        self.image_gen.camera.set_framenum(1) # acquire 1 frame at a time
        self.image_gen.camera.acq_start()
        
        self.imgs = np.zeros([ph,
                              self.image_gen.settings.image_height.val,
                              self.image_gen.settings.image_width.val])
        
        for frame_idx in range(frame_num):
            
            v0 = float(voltages[0][frame_idx])
            v1 = float(voltages[1][frame_idx])
            self.ni_ao_0.AO_device.write_constant_voltage(v0)
            self.ni_ao_1.AO_device.write_constant_voltage(v1)
            time.sleep(0.05) #TODO remove after solving the issue
            self.frame_index = frame_idx
            self.image_gen.camera.acq_start()
            self.img = self.image_gen.camera.get_nparray()
            self.image_gen.camera.acq_stop()
            self.imgs[frame_idx,:,:] = self.img                
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
        
    def update_voltages(self, expected, measured):             
        """
        Updates the voltage indicated in the table
        expected : np.array (float) 3x7 
        measured : np.array (float) 3x7 
        """
        table = self.ui.tableWidget
        rows = table.rowCount() # phases (7)
        cols = table.columnCount() # channels (2)
        
        new_values = np.zeros([rows,cols]) # array with the new values, initialized to zero
        
        # error = ......
              
        # new_values [i,j]  =  .......
        
        
        for j in range(cols): 
            for i in range(rows):
                      val = new_values[i,j] 
                      table.setItem(i,j, QTableWidgetItem(str(val)))  
        
        
        
        
    
    def run(self):
        self.image_gen.read_from_hardware()
        
        if self.settings['calibrate']:
            print('Calibration started')
            for iteration in range(self.settings.iterations.val):
                if self.interrupt_measurement_called:
                    break
                else:
                    self.measure(save_data=False)
                    self.ni_ao_0.stop()
                    self.ni_ao_1.stop()
                    self.cutRoi()
                    if iteration == 0:
                        self.setup_reconstructor()
                    self.calibrate()
                    expected, measured = self.find_phaseshifts()
                    print(f'\nPhases after iteration {iteration}') 
                    with np.printoptions(precision=3, suppress=False):
                        print(f'Expected:\n {expected}')
                        print(f'Measured:\n {measured}')
                    self.update_voltages(expected,measured)
            print('Calibration ended')       
                    
                       
        else:
            """
            If not in calibration mode, acquire frames of measure
            """
            try:          
                self.frame_index = 0
                self.enableROIselection()
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
                        self.measure(True)
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
                      
    def setup_reconstructor(self):
        self.h = HexSimProcessor()  # create reconstruction object 
        self.h.debug = False
        self.h.cleanup = True
        self.h.axial = False
        self.h.usemodulation = True
        self.h.magnification = self.settings['magnification']
        self.h.NA = self.settings['NA']
        self.h.n = self.settings['n']
        self.h.wavelength = self.settings['wavelength']
        self.h.pixelsize = self.settings['pixelsize']
        self.h.alpha = self.settings['alpha']
        self.h.beta = self.settings['beta']
        self.h.w = self.settings['w']
        self.h.eta = self.settings['eta']
        
    def calibrate(self):
        isFindCarrier =True
        if self.settings['gpu']:
            self.h.calibrate_cupy(self.imageRaw, isFindCarrier)       
        else:
            self.h.calibrate(self.imageRaw, isFindCarrier)          
        self.isCalibrated = True
        
        
    def enableROIselection(self):
        """
        If the image has not the size specified in ROIsize,
        listen for click event on the pg.ImageView
        """
        def click(event):
            """
            Resizes imageRaw on click event, to the specified size 'ROI_size'
            around the clicked point.
            """
            ROIsize = self.settings['ROI_size']
            Ly =self.img.shape[-1]
            Lx =self.img.shape[-2]
                
            if self.settings['selectROI'] and (Lx,Ly)!=(ROIsize,ROIsize):
                event.accept()  
                pos = event.pos()
                x = int(pos.x()) #pyqtgraph is transposed
                y = int(pos.y())
                x = max(min(x, Lx-ROIsize//2 ),ROIsize//2 )
                y = max(min(y, Ly-ROIsize//2 ),ROIsize//2 )
                self.settings['roiX']= x
                self.settings['roiY']= y
                if hasattr(self, 'roi'):
                    self.imv.removeItem(self.roi)    
                self.roi = pg.RectROI([x-ROIsize//2,y-ROIsize//2], [ROIsize,ROIsize])
                self.imv.addItem(self.roi)
                
            self.settings['selectROI'] = False
        
        self.imv.getImageItem().mouseClickEvent = click
        self.settings['selectROI'] = True
                                 
                      
    def cutRoi(self):        
        Ly =self.imgs.shape[-1]
        Lx =self.imgs.shape[-2]
        x = self.settings['roiX']
        y = self.settings['roiY']
        ROIsize = self.settings['ROI_size']
        x = max(min(x, Lx-ROIsize//2 ),ROIsize//2 )
        y = max(min(y, Ly-ROIsize//2 ),ROIsize//2 )
        xmin = x - ROIsize//2
        ymin = y - ROIsize//2
        self.imageRaw = self.imgs [:,xmin:xmin+ROIsize, ymin:ymin+ROIsize]
        
        self.settings['selectROI'] = False
        print(f'ROI set to shape: {self.imageRaw.shape}')   


    def find_phaseshifts(self):
        phaseshift = np.zeros((3,7))
        expected_phase = np.zeros((3,7))
    
        for i in range (2):
            phase, _ = self.h.find_phase(self.h.kx[i],self.h.ky[i],self.imageRaw)
            expected_phase[i,:] = np.arange(7) * 2*(i+1) * np.pi / 7
            phaseshift[i,:] = np.unwrap(phase - expected_phase[i,:]) + expected_phase[i,:] - phase[0]
    
        #phaseshift[3] = phaseshift[2]-phaseshift[1]-phaseshift[0]
        return expected_phase, phaseshift
            
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
        self.image_h5 = self.h5_group.create_dataset(name  = 't0000/c0/image', 
                                                  shape = [length, img_size[0], img_size[1]],
                                                  dtype = dtype)
        
        xy_sampling = self.settings['pixelsize'] / self.settings['magnification']
        self.image_h5.attrs['element_size_um'] =  [1.0,xy_sampling,xy_sampling]