#!/usr/bin/env python
import rospy
import numpy as np
import math
import argparse
from duckietown_msgs.msg import  Twist2DStamped
from sensor_msgs.msg import CompressedImage, Image
from cv_bridge import CvBridge, CvBridgeError
from duckietown_utils.jpg import image_cv_from_jpg
from matplotlib import pyplot as plt
import cv2
import sys
import time
import threading
import argparse
import imutils

class andy(object):
	def __init__(self):
		self.node_name = rospy.get_name()

		self.thread_lock = threading.Lock()
		self.active = True

		# to do: initial no-faces-detected as face_detected senario
		self.face_detected = 0

		self.bridge = CvBridge()

		# Publicaiton

		# To do : publish ros message topic: /node_name/car_cmd, datatype: Twist2DStamped 
		#plt.rcParams['figure.figsize'] = (10, 10)
		#plt.rcParams['image.interpolation'] = 'nearest'

		# To do : publish ros message topic: /node_name/image_with_face, datatype: Image 
		self.pub_image_face = rospy.Publisher("~image_with_face", Image, queue_size=1)
		self.pub_image_HSV = rospy.Publisher("~image_with_HSV", Image, queue_size=1)
		self.pub_image_edge = rospy.Publisher("~image_with_edge", Image, queue_size=1)

        # Subscription

		# To do : subscribe ros message topic: /node_name/joystick_car_cmd datatype: Twist2DStamped, callback function: self.cbJoystick

		# To do : subscribe ros message topic: /node_name/image, datatype: CompressedImage, callback function: self.cbImage
		self.sub_image_origin = rospy.Subscriber("andyduck/camera_node/image/compressed", CompressedImage, self.cbImage, queue_size=10)

		# safe shutdown
		rospy.on_shutdown(self.custom_shutdown)

		# timer
		rospy.loginfo("[%s] Initialized " %(rospy.get_name()))

	def custom_shutdown(self):
		rospy.loginfo("[%s] Shutting down..." %self.node_name)

		# Send stop command
		rospy.sleep(0.5) #To make sure that it gets published.
		rospy.loginfo("[%s] Shutdown" %self.node_name)

	def cbImage(self, image_msg):

		if not self.active:
			return

		thread = threading.Thread(target=self.processImage,args=(image_msg,))
		thread.setDaemon(True)
		thread.start()

	def processImage(self, image_msg):
		if not self.thread_lock.acquire(False):
			return

		try:
			self.cbObjectDetect(image_msg)
		finally:
			self.thread_lock.release()
	def cent_in_square(self, cent , box):
		min_x = min(box[0][0],box[1][0],box[2][0],box[3][0])
		min_y = min(box[0][1],box[1][1],box[2][1],box[3][1])
		max_x = max(box[0][0],box[1][0],box[2][0],box[3][0])
		max_y = max(box[0][1],box[1][1],box[2][1],box[3][1])
		if cent[0] > min_x and cent[0] < max_x and cent[1] > min_y and cent[1] < max_y:
			return True
		return False			
	def compare_cir(self, cir , box):
		min_x = min(box[0][0],box[1][0],box[2][0],box[3][0])
		min_y = min(box[0][1],box[1][1],box[2][1],box[3][1])
		max_x = max(box[0][0],box[1][0],box[2][0],box[3][0])
		max_y = max(box[0][1],box[1][1],box[2][1],box[3][1])
		if cir[0] > min_x and cir[0] < max_x and cir[1] > min_y and cir[1] < max_y:
			return True
		return False
	def check_square(self,box):
		dis1 = math.sqrt((box[0][0] - box[1][0])**2 + (box[0][1] - box[1][1])**2)
		dis2 = math.sqrt((box[1][0] - box[2][0])**2 + (box[1][1] - box[2][1])**2)
		for i in box:
			if i[0] <= 10 or i[0] >= 620 or i[1] <= 10 or i[1] >= 470:
				return False
		if 1.2 >= (dis1/dis2) >= 0.83:
			return True
		return False
	def cbObjectDetect(self, image_msg):
		# Decompress image and convert ROS image message to cv image
		narr = np.fromstring(image_msg.data, np.uint8)
		image = cv2.imdecode(narr, cv2.IMREAD_COLOR)
		#image = image_cv_from_jpg(image_msg.data)
		cir = [0,0,0]
		a=[0,0]
		box = [a,a,a,a]

		edges = cv2.Canny(image,100,200)
		hsv = cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
		lowerblue = np.array([110,50,50])
		upperblue = np.array([130,255,255])
		mask2 = cv2.inRange(hsv,lowerblue,upperblue)
		mask = cv2.Canny(mask2,100,200)

		MAXAREA = 18000
		MINAREA = 50

		ap = argparse.ArgumentParser()
		args = vars(ap.parse_args())
		resized = imutils.resize(image, width=300)
		gray1 = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
		gray  = cv2.Canny(gray1,50,200)

		blurred = cv2.GaussianBlur(gray, (5, 5), 0)
		thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY)[1]
 		ratio = image.shape[0] / float(resized.shape[0])
		# find contours in the thresholded image and initialize the
		# shape detector
		cnts = cv2.findContours(thresh.copy(), cv2.RETR_CCOMP  ,cv2.CHAIN_APPROX_SIMPLE)
		cnts = cnts[1]
		sd = ShapeDetector()
		for c in cnts:							
			if MAXAREA >= cv2.contourArea(c) >= MINAREA:
				shape = sd.detect(c)
				if shape is not "unidentified" and shape is not "rectangle":
					M = cv2.moments(c)
					if M["m00"] == 0 :
						break
					cX = int((M["m10"] / M["m00"]) * ratio)
					cY = int((M["m01"] / M["m00"]) * ratio)
					c = c.astype("float")
					c *= ratio
					c = c.astype("int")
					if shape is "square" or shape is "triangle":
						rect = cv2.minAreaRect(c)
					#rect = ((rect[0][0] * self.scale_down, rect[0][1] * self.scale_down), (rect[1][0] * self.scale_down, rect[1][1] * self.scale_down), rect[2])
						box = cv2.boxPoints(rect)
						box = np.int0(box)
						if self.check_square(box):
							cv2.drawContours(image,[box], 0, (255, 0, 0), 2)
							cv2.drawContours(image, [c], -1, (0, 255, 0), 2)
							print box
							cv2.putText(image, shape, (cX, cY), cv2.FONT_HERSHEY_SIMPLEX,0.5, (255, 255, 255), 2)
    
		image_msg_out = self.bridge.cv2_to_imgmsg(image, "bgr8")
		#image_msg_out_hsv = self.bridge.cv2_to_imgmsg(mask2, "8UC1")
		image_msg_out_edge = self.bridge.cv2_to_imgmsg(gray)
		image_msg_out.header.stamp = image_msg.header.stamp


		self.pub_image_face.publish(image_msg_out)
		#self.pub_image_HSV.publish(image_msg_out_hsv)
		#self.pub_image_edge.publish(image_msg_out_edge)
 
class ShapeDetector:
	def __init__(self):
		pass
 
	def detect(self, c):
		# initialize the shape name and approximate the contour
		shape = "unidentified"
		peri = cv2.arcLength(c, True)
		c1 = cv2.convexHull(c)
		approx = cv2.approxPolyDP(c1, 0.04 * peri, True)

		# if the shape is a triangle, it will have 3 vertices
		if len(approx) == 3:
			shape = "triangle"
 
		# if the shape has 4 vertices, it is either a square or
		# a rectangle
		elif len(approx) == 4:
			# compute the bounding box of the contour and use the
			# bounding box to compute the aspect ratio
			(x, y, w, h) = cv2.boundingRect(approx)
			ar = w / float(h)
 
			shape = "square" if ar >= 0.7 and ar <= 1.3 else "rectangle"
 			if h < 5 or w < 5:
 				shape = "unidentified" 

if __name__ == "__main__":

	# to do: initial a node named "face_detector_X", X= you duckiebot name
	rospy.init_node("face_detector",anonymous=False)

	face_detector_wama_node = andy()
	rospy.spin()