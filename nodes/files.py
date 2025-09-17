#import numpy as np
#import random
import folder_paths
import os
import re
import csv
from pathlib import Path
# from logging import Logger

# logger = Logger.getlogger()
root_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.abspath(os.path.join(root_dir, "../data"))

class KN_GetFileCountInOutputFolder:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
            "path": ("STRING",{"Tooltip":"Path under the configured output directory"}),
            },
        }
               
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("File Counter",)
	
    FUNCTION = "getCount"
	
    CATEGORY = "KaleidiaNodes/FileNodes"
	DESCRIPTION = "This node counts all png files in the given path under the configured output directory and then returns either the amount of files or if the files have a prefix counter, the highest counter if it is higher then the amount."
	
    def getCount(self,path):
        folderpath = os.path.join(folder_paths.output_directory,path)
        folderpath = Path(folderpath)
        print(f"Counting files in directory: {folderpath} with file types: png")
        counter: int = 0
        lastFiles: list = list()

        if not folderpath.exists() or not folderpath.is_dir():
            print(f"Directory not there or empty, returning counter with 0")
            return(0,)

        lastFiles = [f for f in os.listdir(folderpath) if f.lower().endswith(".png")]
        counter = len(lastFiles)

        if len(lastFiles) == 0:
            print(f"Directory empty, returning counter with 0")
            return(0,)

        prefix = 0        
        for filename in lastFiles:
            match = re.match(r"^0*(\d+)",filename)
            if match:
                num = int(match.group(1))
                prefix = max(prefix, num)

        counter = max(counter, prefix)
        
        print(f"Directory contains {counter} files.")
        return (counter,)
        
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

class KN_CSV_Reader:
    """
    Scan Folder for csv files and then list them.
    Parse file and 
    """

    data_folder = Path(csv_path)
    rows_cache = {}

    @classmethod
    def load_csv(cls, csv_file):
        file_path = cls.data_folder / csv_file
        if not file_path.exists():
            return ["file not found"]
        try:
            with open(file_path, newline = "", encoding = "utf-8") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if len(row) >= 3 and row[0].strip() and not row[0].startswith(">>>>>>")]
                if len(rows) < 2:
                    return ["no rows"]
                
                return [row[0] for row in rows[1:]] #if rows_data else ["no rows"]
        except Exception as e:
            return [f"error: {e}"]

    @classmethod
    def INPUT_TYPES(cls):
        csv_files = [f.name for f in cls.data_folder.glob("styles.csv")] or ["<no csv files>"]
        default_file = csv_files[0] if csv_files else "no files"
        selections = cls.load_csv(default_file) if default_file != "no files" else ["select csv file"]

        return {
            "required": {
                "csv_file": (csv_files,{"default": "styles.csv"},),
                "selection": (selections,{"default": "Empty"}, ),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("Prompt", "negative Prompt")
    OUTPUT_IS_LIST = (False, False)
    OUTPUT_TOOLTIPS = ("Positive Prompt.\n","Negative Prompt")

    FUNCTION = "browse_csv"

    CATEGORY = "KaleidiaNodes/FileNodes"
    DESCRIPTION = "Loads rows from selected csv file based on UI selection.\nFirst column is always used to provide labels for UI."

    def browse_csv(self, csv_file, selection):
        file_path = self.data_folder / csv_file
        if not file_path.exists():
            return ("not found","")

        try:
            with open(file_path, newline = "", encoding = "utf-8") as f:
                reader = csv.reader(f)
                rows = [row for row in reader if len(row) >= 3 and row[0].strip()]
                #print(f"rows: {rows}, name: {rows[0]}")
                if len(rows) < 2:
                    return ("no rows","")

                for row in rows[1:]:
                    #print(f"name: {row[0]} vs selection: {selection}")
                    if row[0].strip() == str(selection).strip():
                        print(f"{row[0]} - {row[1]} - {row[2]}")
                        return (row[1],row[2])

                return (f"no match in {csv_file} for {selection}","")
        except Exception as e:
            return (f"error: {e}",f"error: {e}")

#-------------------------------------------------------------------------------------
# helpers
#-------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------

