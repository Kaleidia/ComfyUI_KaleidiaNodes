# KaleidiaNodes
A simple set of nodes I created for comfyui to make things easier for me.

There are two sets of nodes so far: file nodes and string nodes.

## File Nodes
There are two nodes here so far, one for counting png files in the comfy output directory and one for reading a csv file within the project's file structure.

### File Counter
<img width="472" height="119" alt="image" src="https://github.com/user-attachments/assets/7cc3027c-bd80-4d9d-881d-27b88986c0c4" />
This is a simple node with an input of a path or just directory name and an output of type integer for the count of files there. 
It goes to the configured output directory and adds a directory if none of the provided name is present or goes into the provided folder and counts all png files present in there. It returns either that amount or the highest prefix in the beginning of files as I like to have a counter there ("00000 - prompt.png" is my preferred output file name). In the case that there are 8 files in the directory and the highest prefix is 00010, it will return 11 (the previous highest +1).

### CSV Reader
<img width="310" height="195" alt="image" src="https://github.com/user-attachments/assets/f31cc8da-7e52-46b8-a97d-f4babd3025bf" />
This node was supposed to be general csv file reader for files with the structure "name,prompt,negative_prompt". Due to the static nature of nodes in just python, it was changed and now reads the file "styles.csv" from the provided data directory. It then lists all names from that file in a combo / selection box and returns the prompt and negative prompt texts in their respective outputs. Further use of these outputs depends on the individual setup, for my use case, I replace the word *prompt* with an additional prompt providing subject and further info. All the positive sample prompts have the word *prompt* in the positive part and the negative prompt can be appended to a general negative prompt.

## String Nodes
There are three string nodes so far, one that formats an integer into a string with optional leading zeroes, one that generates a random integer and gives it out as either int or string and the the same with a floating point number.

### Int To String
<img width="448" height="282" alt="image" src="https://github.com/user-attachments/assets/9678a13b-72a0-43d7-a270-ce5bec3db370" />
This node gets an integer as input and can format it to a specified number of digits adding leading zeroes. It then outputs that number either as a formatted string or as an integer (basically passing the int through to be used for other calculations later). The added zeroes are optional and can be turned off with the *use digits* switch at the buttom. That does not change the digits of the provided integer.

### Random Int to String
This node generates a random integer in the provided range from min to max and outputs that as a string.
### Random Float to String
Similar to the integer node, it generates a random float in the range and returns the formatted string.
