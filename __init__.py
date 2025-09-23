from .nodes.toString import *
from .nodes.files import *
from .nodes.prompt import *

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "FormatIntToString": KN_FormatIntToString,
    "RandomIntToString": KN_RandomIntToString,
    "RandomFloatToString": KN_RandomFloatToString,
    "GetFileCountInOutputFolder": KN_GetFileCountInOutputFolder,
    "LoadCSV": KN_CSV_Reader,
    "DynamicPromptNode": KN_DynamicPromptNode,
    "DynamicPromptNodeEXT": KN_DynamicPromptNode_Ext,
}
 
# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "FormatIntToString": "Format Int To String",
    "RandomIntToString": "Random Int To String",
    "RandomFloatToString": "Random Float To String",
    "GetFileCountInOutputFolder": "Get Counter In Output Folder",
    "LoadCSV": "Load Prompt from CSV",
    "DynamicPromptNode": "Dynamic Prompt",
    "DynamicPromptNodeEXT": "Dynamic Prompt Extended (Experimental)",
    }
    
print("Kaleidia Nodes: \033[92mLoaded\033[0m")