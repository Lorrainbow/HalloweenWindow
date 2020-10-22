# HalloweenWindow
This code runs a raspberry pi using multiprocessing to 
- play a light animation
- detect motion from the raspberry pi camera
- control another set of lights over IR

When it detects motion it changes the light animation on both the light strip attached to it and using an IR transmitter to control a bigger independent light strip. 

Before you can run this code you need to create the JSON files for the IR code. Run GoIR.py -r -g 17 -f colourRed.json 1 to record the remote button presses. The script will prompt you when to press the right button. Do it again for colourGreen.json. 

Demo here:
https://www.element14.com/community/community/halloween/blog/2020/10/22/interactive-halloween-window


Uploading the code as I found it difficult to find code that worked with python3
