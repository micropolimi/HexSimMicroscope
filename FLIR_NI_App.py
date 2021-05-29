# -*- coding: utf-8 -*-
"""
Created on Thu May  6 15:50:58 2021

@author: LAB
"""


from ScopeFoundry import BaseMicroscopeApp

class FLIR_NI_App(BaseMicroscopeApp):

    # this is the name of the microscope that ScopeFoundry uses 
    # when storing data
    name = 'flir_ni_app'
    
    # You must define a setup function that adds all the 
    #capablities of the microscope and sets default settings
    def setup(self):
        
        #Add App wide settings
        
        #Add hardware components
        print("Adding Hardware Components")
        from NIdaqmx_ScopeFoundry.ni_ao_hardware import NI_AO_hw
        #from NIdaqmx_ScopeFoundry.ni_do_hardware import NI_DO_hw
        #from NIdaqmx_ScopeFoundry.ni_co_hardware import NI_CO_hw
        from Flir_ScopeFoundry.camera_hw import FlirHW
        
        self.add_hardware(NI_AO_hw(self, name='Analog_Output_0'))
        self.add_hardware(NI_AO_hw(self, name='Analog_Output_1'))
        #self.add_hardware(NI_DO_hw(self))
        #self.☺add_hardware(NI_CO_hw(self))
        self.add_hardware(FlirHW(self))
           
        # Add measurement components
        print("Create Measurement objects")
        
        from HexSIM_Microscope.FLIR_NI_measure import FlirNImeasure
        self.add_measurement(FlirNImeasure(self))
        
        from HexSimAnalyser.HexSimAnalyser_measurement import HexSimAnalysis
        self.add_measurement(HexSimAnalysis)
        
        
        # show ui
        self.ui.show()
        self.ui.activateWindow()


if __name__ == '__main__':
    import sys
    
    app = FLIR_NI_App(sys.argv)
    app.settings_load_ini(".\\Settings\\hexSIM.ini")
    
    sys.exit(app.exec_())