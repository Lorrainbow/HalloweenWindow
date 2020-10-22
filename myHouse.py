
#!/usr/bin/python

# original script adopted from brainflakes
# www.raspberrypi.org/phpBB3/viewtopic.php?f=43&t=45235
# You need to install PIL
# type "sudo apt-get install python-imaging-tk" in an terminal window to do this

#You need the neopixel library
#type "sudo pip3 install adafruit-circuitpython-neopixel"
#this page has a great sample code to start with: https://learn.adafruit.com/adafruit-neopixel-uberguide/python-circuitpython

#on the pi I created a directory called window and put this code in there
#you also need a directory called picam to store your images
#like so: /home/pi/window/picam"

#Run this script with sudo python3 

#What it does!
#This script uses the raspberry pi camera to detect motion and change a light strip's colour
#It uses multiprocessing to check for motion and play light animations at the same time
#When motion is detected it changes the animation on the lightstrip AND it sends an IR signal to another strip of lights!

from multiprocessing import Process, Value
import subprocess
import os
import time
from datetime import datetime
from PIL import Image
import random
import board
import neopixel
import io
from itertools import zip_longest
import json
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html

#set personDetected to false
personDetected = Value("b",0)

#setup the neopixel stuff. D18 is the pin the neopixel strip is connected to on the pi
pixel_pin = board.D10
num_pixels = 151
ORDER = neopixel.GRB
on_time = 0.04
pixels = neopixel.NeoPixel(
    pixel_pin, num_pixels, brightness=1.0, auto_write=False, pixel_order=ORDER
)

#my strip is 3 columns, numbered like so
#column1 = 0-38 (39)
#column2 = 47-87 (41)
#column3 = 98-137 (39)
column1=[]
column2=[]
column3=[]

#creating a list for each column cause that's how i roll
for x in range(39):
    column1.append(x)
for x in range(86, 46,-1):
    column2.append(x)
for x in range(99,138):
    column3.append(x)

#lovely colours
colour1 = (255,0,0)
colour2 = (255,255,0)
colour3 = (255,100,125)	
colour4 = (255,0,255)
colour5 = (0,255,255)

gap = 100
GAP_MS = gap
GAP_S      = GAP_MS  / 1000.0


# Motion detection settings:
# Threshold          - how much a pixel has to change by to be marked as "changed"
# Sensitivity        - how many changed pixels before capturing an image, needs to be higher if noisy view
# ForceCapture       - whether to force an image to be captured every forceCaptureTime seconds, values True or False
# filepath           - location of folder to save photos
# filenamePrefix     - string that prefixes the file name for easier identification of files.
# diskSpaceToReserve - Delete oldest images to avoid filling disk. How much byte to keep free on disk.
# cameraSettings     - "" = no extra settings; "-hf" = Set horizontal flip of image; "-vf" = Set vertical flip; "-hf -vf" = both horizontal and vertical flip
threshold = 10
sensitivity = 50
forceCapture = True
forceCaptureTime = 60 * 60 # Once an hour
filepath = "/home/pi/window/picam"
filenamePrefix = "capture"
diskSpaceToReserve = 40 * 1024 * 1024 # Keep 40 mb free on disk
cameraSettings = ""

# settings of the photos to save
saveWidth   = 1296
saveHeight  = 972
saveQuality = 15 # Set jpeg quality (0 to 100)

# Test-Image settings
testWidth = 100
testHeight = 75

# this is the default setting, if the whole image should be scanned for changed pixel
testAreaCount = 1
testBorders = [ [[1,testWidth],[1,testHeight]] ]  # [ [[start pixel on left side,end pixel on right side],[start pixel on top side,stop pixel on bottom side]] ]
# testBorders are NOT zero-based, the first pixel is 1 and the last pixel is testWith or testHeight

# with "testBorders", you can define areas, where the script should scan for changed pixel
# for example, if your picture looks like this:
#
#     ....XXXX
#     ........
#     ........
#
# "." is a street or a house, "X" are trees which move arround like crazy when the wind is blowing
# because of the wind in the trees, there will be taken photos all the time. to prevent this, your setting might look like this:

# testAreaCount = 2
# testBorders = [ [[1,50],[1,75]], [[51,100],[26,75]] ] # area y=1 to 25 not scanned in x=51 to 100

# even more complex example
# testAreaCount = 4
# testBorders = [ [[1,39],[1,75]], [[40,67],[43,75]], [[68,85],[48,75]], [[86,100],[41,75]] ]

# in debug mode, a file debug.bmp is written to disk with marked changed pixel an with marked border of scan-area
# debug mode should only be turned on while testing the parameters above
debugMode = False # False or True

# Capture a small test image (for motion detection)
def captureTestImage(settings, width, height):
    command = "raspistill %s -w %s -h %s -t 200 -e bmp -n -o -" % (settings, width, height)
    imageData = io.BytesIO()
    imageData.write(subprocess.check_output(command, shell=True))
    imageData.seek(0)
    im = Image.open(imageData)
    buffer = im.load()
    imageData.close()
    return im, buffer

# Save a full size image to disk
def saveImage(settings, width, height, quality, diskSpaceToReserve):
    keepDiskSpaceFree(diskSpaceToReserve)
    time = datetime.now()
    filename = filepath + "/" + filenamePrefix + "-%04d%02d%02d-%02d%02d%02d.jpg" % (time.year, time.month, time.day, time.hour, time.minute, time.second)
    #subprocess.call("raspistill %s -w %s -h %s -t 200 -e jpg -q %s -n -o %s" % (settings, width, height, quality, filename), shell=True)
    #print ("Captured %s" % filename)

# Keep free space above given level
def keepDiskSpaceFree(bytesToReserve):
    if (getFreeSpace() < bytesToReserve):
        for filename in sorted(os.listdir(filepath + "/")):
            if filename.startswith(filenamePrefix) and filename.endswith(".jpg"):
                os.remove(filepath + "/" + filename)
                print ("Deleted %s/%s to avoid filling disk" % (filepath,filename))
                if (getFreeSpace() > bytesToReserve):
                    return

# Get available disk space
def getFreeSpace():
    st = os.statvfs(filepath + "/")
    du = st.f_bavail * st.f_frsize
    return du

def cameraCode(person):
	# Get first image
	image1, buffer1 = captureTestImage(cameraSettings, testWidth, testHeight)

	# Reset last capture time
	lastCapture = time.time()

	while (True):    
		# Get comparison image
		image2, buffer2 = captureTestImage(cameraSettings, testWidth, testHeight)

		# Count changed pixels
		changedPixels = 0
		takePicture = False		

		if (debugMode): # in debug mode, save a bitmap-file with marked changed pixels and with visible testarea-borders
			debugimage = Image.new("RGB",(testWidth, testHeight))
			debugim = debugimage.load()

		for z in range(0, testAreaCount): # = xrange(0,1) with default-values = z will only have the value of 0 = only one scan-area = whole picture
			for x in range(testBorders[z][0][0]-1, testBorders[z][0][1]): # = xrange(0,100) with default-values
				for y in range(testBorders[z][1][0]-1, testBorders[z][1][1]):   # = xrange(0,75) with default-values; testBorders are NOT zero-based, buffer1[x,y] are zero-based (0,0 is top left of image, testWidth-1,testHeight-1 is botton right)
					if (debugMode):
						debugim[x,y] = buffer2[x,y]
						if ((x == testBorders[z][0][0]-1) or (x == testBorders[z][0][1]-1) or (y == testBorders[z][1][0]-1) or (y == testBorders[z][1][1]-1)):
							# print "Border %s %s" % (x,y)
							debugim[x,y] = (0, 0, 255) # in debug mode, mark all border pixel to blue
					# Just check green channel as it's the highest quality channel
					pixdiff = abs(buffer1[x,y][1] - buffer2[x,y][1])
					if pixdiff > threshold:
						changedPixels += 1
						if (debugMode):
							debugim[x,y] = (0, 255, 0) # in debug mode, mark all changed pixel to green
					# Save an image if pixels changed
					if (changedPixels > sensitivity):
						takePicture = True # will shoot the photo later
					if ((debugMode == False) and (changedPixels > sensitivity)):
						break  # break the y loop
				if ((debugMode == False) and (changedPixels > sensitivity)):
					break  # break the x loop
			if ((debugMode == False) and (changedPixels > sensitivity)):
				break  # break the z loop

		if (debugMode):
			debugimage.save(filepath + "/debug.bmp") # save debug image as bmp
			print ("debug.bmp saved, %s changed pixel" % changedPixels)
		# else:
		#     print "%s changed pixel" % changedPixels

		
		# Check force capture
		if forceCapture:
			if time.time() - lastCapture > forceCaptureTime:
				takePicture = True

		
		if takePicture:
			person.value = 1			
			lastCapture = time.time()			
			#you don't have to save the image! it's just going to be dark with a spot of light...
	#		saveImage(cameraSettings, saveWidth, saveHeight, saveQuality, diskSpaceToReserve)
		else:			
			person.value = 0

		# Swap comparison buffers
		image1 = image2
		buffer1 = buffer2

		
def carrier(gpio, frequency, micros):
   """
   Generate carrier square wave.
   """
   wf = []
   cycle = 1000.0 / frequency
   cycles = int(round(micros/cycle))
   on = int(round(cycle / 2.0))
   sofar = 0
   for c in range(cycles):
      target = int(round((c+1)*cycle))
      sofar += on
      off = target - sofar
      sofar += off
      wf.append(pigpio.pulse(1<<gpio, 0, on))
      wf.append(pigpio.pulse(0, 1<<gpio, off))
   return wf

		
		
		
def colourWindow(column,colour, start, stop):
	for x in range(start, stop+1):		
		pixels[column[x]] = colour	
		
def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        r = g = b = 0
    elif pos < 85:
        r = int(pos * 3)
        g = int(255 - pos * 3)
        b = 0
    elif pos < 170:
        pos -= 85
        r = int(255 - pos * 3)
        g = 0
        b = int(pos * 3)
    else:
        pos -= 170
        r = 0
        g = int(pos * 3)
        b = int(255 - pos * 3)
    return (r, g, b) if ORDER in (neopixel.RGB, neopixel.GRB) else (r, g, b, 0)


def rainbow_cycle(wait):
    for j in range(255):
        for i in range(num_pixels):
            pixel_index = (i * 256 // num_pixels) + j
            pixels[i] = wheel(pixel_index & 255)
        pixels.show()
        time.sleep(wait)

#this is the code that runs when motion is detected
def goRed():	
	pixels.fill((0,0,0))
	pixels.show()
	time.sleep(1)
	

	#turn the haunted house red
	for x in range(7):	
		#run a script that transmits using IR with its red code
		os.system("python3 GoIR.py -p -g 27 -f colourRed.json 1")
		pixels.fill((255,0,0))
		pixels.show()
		time.sleep(0.3)
		#run a script that transmits using IR with its green code
		os.system("python3 GoIR.py -p -g 27 -f colourGreen.json 1")
		pixels.fill((0,255,0))
		pixels.show()
		time.sleep(0.3)
	#os.system("sudo killall pigpiod")
	time.sleep(1)
	
	pixels.fill((0,0,0))
	pixels.show()
	
	
#multiprocessing loveliness. the process starts now and will interupt when personDetected changes
p = Process(target=cameraCode,args=(personDetected,))
p.start()
os.system("sudo pigpiod")

#go forever, might want to change this to a time limited loop
while True:	
	now = datetime.now()
	current_hour = now.strftime("%H")
	
	if current_hour >= 23 or current_hour <= 18:
		pixels.fill((0,0,0))
		pixels.show()
		time.sleep(300)	
		
	else:
		#middle column
		#colourWindow(column2,colour3,0,11)		
			
		#loop the windows
		for x in range(4):
			
			#check for a person
			if personDetected.value == 1:
				goRed()
		
			#bottom right window
			colourWindow(column1,colour1,7,10)
			#top right
			colourWindow(column1,colour2,18,22)
			#bottom left window
			colourWindow(column3,colour4,7,10)
			#top left
			colourWindow(column3,colour5,18,22)


			#bottom right window
			colourWindow(column1,colour5,7,10)
			#top right
			colourWindow(column1,colour2,18,22)
			#bottom left window
			colourWindow(column3,colour4,7,10)
			#top left
			colourWindow(column3,colour1,18,22)

			pixels.show()
			time.sleep(0.4)
		

			#bottom right window
			colourWindow(column1,colour5,7,10)
			#top right
			colourWindow(column1,colour4,18,22)
			#bottom left window
			colourWindow(column3,colour2,7,10)
			#top left
			colourWindow(column3,colour1,18,22)
		
			#bottom right window
			colourWindow(column1,colour1,7,10)
			#top right
			colourWindow(column1,colour4,18,22)
			#bottom left window
			colourWindow(column3,colour2,7,10)
			#top left
			colourWindow(column3,colour5,18,22)
		
			pixels.show()
			time.sleep(0.4)
			
	#	goRed()
		#circle the windows
		for x in range(4):
			#check for a person
			if personDetected.value == 1:
				goRed()
		
			#bottom right window
			colourWindow(column1,colour1,7,10)
			#top right
			colourWindow(column1,colour4,18,22)
			#bottom left window
			colourWindow(column3,colour2,7,10)
			#top left
			colourWindow(column3,colour5,18,22)
		
			pixels.show()
			time.sleep(0.3)	
		
			#bottom right window
			colourWindow(column1,colour4,7,10)
			#top right
			colourWindow(column1,colour5,18,22)
			#bottom left window
			colourWindow(column3,colour1,7,10)
			#top left
			colourWindow(column3,colour2,18,22)
		
			pixels.show()
			time.sleep(0.3)	

			#bottom right window
			colourWindow(column1,colour5,7,10)
			#top right
			colourWindow(column1,colour2,18,22)
			#bottom left window
			colourWindow(column3,colour4,7,10)
			#top left
			colourWindow(column3,colour1,18,22)
		
			pixels.show()
			time.sleep(0.3)	
		
			#bottom right window
			colourWindow(column1,colour2,7,10)
			#top right
			colourWindow(column1,colour1,18,22)
			#bottom left window
			colourWindow(column3,colour5,7,10)
			#top left
			colourWindow(column3,colour4,18,22)
		
			pixels.show()
			time.sleep(0.3)	
		
		if personDetected.value == 1:
			goRed()
		
		#rain
		start = 38
		for x in range(38,0,-1):
			#check for a person
		
			if x <= start - 2:
				pixels[column1[x+2]] = (0,0,0)
				pixels[column2[x+2]] = (0,0,0)
				pixels[column3[x+2]] = (0,0,0)
			
			pixels[column1[x]] = (255,255,255)
			pixels[column2[x]] = (255,255,255)
			pixels[column3[x]] = (255,255,255)
			pixels.show()
			time.sleep(0.07)
		if personDetected.value == 1:
			goRed()
		
			
		for x in range(3,0,-1):
			pixels[column1[x]] = (0,0,0)
			pixels[column2[x]] = (0,0,0)
			pixels[column3[x]] = (0,0,0)	
			pixels.show()

		pixels[86] = (0,0,0)
		pixels.show()
		
		#needs more cool animations
