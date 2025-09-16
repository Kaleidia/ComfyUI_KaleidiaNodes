import numpy as np
import random
import folder_paths
#import os
#import re

#-------------------------------------------------------------------------------------
# To String Nodes
#-------------------------------------------------------------------------------------
class KN_FormatIntToString:
#    def __init__(self):
#        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
			"number_digits": ("INT", {"default":4, "min":1,"max":20,"step":1}),
            "initial_int": ("INT", {"forceInput":True}),
			"use_digits": ("BOOLEAN", {"default":True}),
            },
        }
 
    RETURN_TYPES = ("STRING",'INT')
    #RETURN_LINES = ("Text","Int")
 
    FUNCTION = "convert2String"
 
    #OUTPUT_NODE = False
 
    CATEGORY = "KaleidiaNodes/FormatNodes"
 
    def convert2String(self, initial_int, number_digits=4, use_digits=True ):
        if use_digits:
            return (format(initial_int, f'0{number_digits}d'),initial_int)
        else:
            return (f'{initial_int}',initial_int)
 
class KN_RandomIntToString:
#    def __init__(self):
#        pass
		
    def INPUT_TYPES():
        return {
            "required": {
            "min": ("INT",{"default":0,"min":-100,"step":1}),
            "max": ("INT",{"default":1,"step":1}),
            "seed": SEED_INPUT(),
            },
        }

    RETURN_TYPES = ("STRING",)
	
    FUNCTION = "randomInt"
	
    CATEGORY = "KaleidiaNodes/FormatNodes"
	
    def randomInt(self,min,max,seed):
        rng = np.random.default_rng()
        with KN_SeedContext(seed):
            outputInt = rng.integers(low=min, high=max, endpoint=True)
        outputStr ="{:d}".format(outputInt)
        print(outputStr)
        return (outputStr,)
        
class KN_RandomFloatToString:
#    def __init__(self):
#        pass
		
    def INPUT_TYPES():
        return {
            "required": {
            "min": ("FLOAT",{"default":0.0,"min":-100.0,"step":0.1}),
            "max": ("FLOAT",{"default":1.0,"step":0.1}),
            "seed": SEED_INPUT(),
            },
        }

    RETURN_TYPES = ("STRING",)
	
    FUNCTION = "randomFloat"
	
    CATEGORY = "KaleidiaNodes/FormatNodes"
	
    def randomFloat(self,min,max,seed):
        rng = np.random.default_rng(seed)
        outputFloat = rng.uniform(low=min, high=max)
        outputStr ="{:.2f}".format(outputFloat)
        print(outputStr)
        return (outputStr,)
        
#-------------------------------------------------------------------------------------
        

#-------------------------------------------------------------------------------------
# helpers
#-------------------------------------------------------------------------------------
class KN_SeedContext():
    """
    Context Manager to allow one or more random numbers to be generated, optionally using a specified seed, 
    without changing the random number sequence for other code.
    """
    def __init__(self, seed=None):
        self.seed = seed
    def __enter__(self):
        self.state = random.getstate()
        if self.seed:
            random.seed(self.seed)
    def __exit__(self, exc_type, exc_val, exc_tb):
        random.setstate(self.state)

def SEED_INPUT():
    with KN_SeedContext(None):
        return ("INT",{"default": random.randint(1,999999999), "min": 0, "max": 0xffffffffffffffff})
        
#-------------------------------------------------------------------------------------
