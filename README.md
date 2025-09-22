# KaleidiaNodes
A simple set of nodes I created for comfyui to make things easier for me.

There are two sets of nodes so far: file nodes, string nodes and a random prompt node.

## File Nodes
There are two nodes here so far, one for counting png files in the comfy output directory and one for reading a csv file within the project's file structure.

### File Counter
<img width="472" height="119" alt="image" src="https://github.com/user-attachments/assets/7cc3027c-bd80-4d9d-881d-27b88986c0c4" />

This is a simple node with an input of a path or just directory name and an output of type integer for the count of files there. 
It goes to the configured output directory and adds a directory if none of the provided name is present or goes into the provided folder and counts all png files present in there. It returns either that amount or the highest prefix in the beginning of files as I like to have a counter there ("00000 - prompt.png" is my preferred output file name). In the case that there are 8 files in the directory and the highest prefix is 00010, it will return 11 (the previous highest +1).

### CSV Reader
<img width="310" height="195" alt="image" src="https://github.com/user-attachments/assets/f31cc8da-7e52-46b8-a97d-f4babd3025bf" />

This node was supposed to be general csv file reader for files with the structure "name,prompt,negative_prompt". Due to the static nature of nodes in just python, it was changed and now reads the file "styles.csv" from the provided data directory. It then lists all names from that file in a combo / selection box and returns the prompt and negative prompt texts in their respective outputs. Further use of these outputs depends on the individual setup, for my use case, I replace the word *prompt* with an additional prompt providing subject and further info. All the positive sample prompts have the word *prompt* in the positive part and the negative prompt can be appended to a general negative prompt.

#### Custom Styles or Other Applications
There are numerous ways to use this node apart from just providing styles. You can extent or replace the entries in the styles.csv file however you like. The node just reads the first column as the name, the second as a prompt or first output and the third as a negative prompt or second output. As long as the structure is kept like this, there should be no problem with loading the file. Any additional columns should be ignored. Columns that start with *>>>>>>* are used in the file to organize different groups of styles, those are also ignored in the parsing process.

Sadly due to the static nature of the python nodes and me not tackling js to make it more dynamic, the filename is hardcoded at this point and no other file in the data folder will be loaded. 

Despite the name, the file can also be used to save and load reusable prompts with positive and negative parts. 

## String Nodes
There are three string nodes so far, one that formats an integer into a string with optional leading zeroes, one that generates a random integer and gives it out as either int or string and the the same with a floating point number.

### Int To String
<img width="448" height="282" alt="image" src="https://github.com/user-attachments/assets/9678a13b-72a0-43d7-a270-ce5bec3db370" />

This node gets an integer as input and can format it to a specified number of digits adding leading zeroes. It then outputs that number either as a formatted string or as an integer (basically passing the int through to be used for other calculations later). The added zeroes are optional and can be turned off with the *use digits* switch at the bottom. That does not change the digits of the provided integer.

### Random Int to String
This node generates a random integer in the provided range from min to max and outputs that as a string.
### Random Float to String
Similar to the integer node, it generates a random float in the range and returns the formatted string.

## Random Prompt nodes
There is one node for random input so far. It can handle {...|...|...} as well as wildcards in from of txt, yaml and json files. For txt files, it can find them in subfolders and can handle the * for selecting all files in a folder.
The node searches for wildcards in the standard wildcard folder under the root directory of ComfyUI. Json and yaml files can be used if they are inside that folder, nesting them inside subfolders is planned for future releases.

<img width="443" height="278" alt="image" src="https://github.com/user-attachments/assets/d7f85b93-43d2-4b92-b37c-98424e3eb963" />

There are two modes: random and sequencial
### Random
This mode just gathers all possible options for the expression and picks a random result.
### Sequencial
This mode tries to pick results in order of all possible options. In case of nested terms "a {{blue|red} car|{yellow|green} bike}" it will create results like: "a blue car", "a red car", "a yellow bike" and "a green bike" before starting from the beginning in the same order. !Note: this mode has some problems with too many nestings and just get the first result in wildcard categories (for yaml files). It is still experimental for the squencial mode.
