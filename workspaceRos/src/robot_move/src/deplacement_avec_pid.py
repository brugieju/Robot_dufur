#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 10 12:54:53 2018

@author: antony
"""

NodePictureName1 = "/rrbot/camera1/camera_info"
NodePictureName2 = "/rrbot/cameraBras/camera_info"
NodePicture1 = "/rrbot/camera1/image_raw/compressed"
NodePicture2 = "/rrbot/cameraBras/image_raw/compressed"
NodeCommande = "/cmd_vel"

import os
import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64
from sensor_msgs.msg import CameraInfo
from sensor_msgs.msg import CompressedImage
from getAngleHauteur import getAngle
from detection_color import detect
from setArm import setL,setTheta
import numpy as np
import cv2
from simple_pid import PID

ANGLE_MAX = 0.1
ANGLE_MIN = -0.1
HAUTEUR = -490 # pixels
EPSILON_HAUTEUR = 20 

# Calibration
#d1 =   --> h1 = ?
#d2 =   --> h2 = ?
#h=f(d)=ad+b
#a=(h2-h1)/(d2-d1)
#b = h1-a*d1

class data_getting():
    
    def __init__(self):
        
        print('Init the variables')
        
        self.arreter = 0
        self.img1 = None
        self.img2 = None
        self.matrice1 = None
        self.matrice2 = None
        self.angle = None
        self.hauteur = None
        self.cx = None
        self.cy = None
        self.laserize = False
        self.pidangle = PID(0.07, 0.001, 0.005, setpoint=0)
        self.pidangle.output_limits = (-0.1, 0.1)
        self.pub = rospy.Publisher(NodeCommande, Twist, queue_size=10)
        self.consigne = Twist()
        
        print(" Init the subscribers ")
        
        self.listener_mat1 = rospy.Subscriber(NodePictureName1, CameraInfo, self.callback_matrice1)	
        self.listener_mat2 = rospy.Subscriber(NodePictureName2, CameraInfo, self.callback_matrice2)
        self.listener_img1 = rospy.Subscriber(NodePicture1, CompressedImage, self.callback_img1)
        self.listener_img2 = rospy.Subscriber(NodePicture2, CompressedImage, self.callback_img2)
        self.listener_img2 = rospy.Subscriber(NodeCommande, Twist, self.callback_cmd)
        self.publisher_angle = rospy.Publisher('rrbot/joint1_position_controller/command', Float64)
        self.publisher_L = rospy.Publisher('rrbot/joint1_position_controller/command', Float64)

    ## Callback pour les suscribers    
    def callback_matrice1(self,data):
        self.matrice1 = np.array(data.K).reshape(3,3)
        
    def callback_matrice2(self,data):
        self.matrice2 = np.array(data.K).reshape(3,3)	
        
    def callback_img1(self,data):
        if self.matrice1 is None:
            return
        rawpic1 = data.data
        np_arr = np.fromstring(rawpic1, np.uint8)
        self.img1 =  cv2.undistort(cv2.imdecode(np_arr, cv2.IMREAD_COLOR),self.matrice1, None)
        
    def callback_img2(self,data):
        if self.matrice2 is None:
            return
        rawpic2 = data.data
        np_arr = np.fromstring(rawpic2, np.uint8)
        self.img2 =  cv2.undistort(cv2.imdecode(np_arr, cv2.IMREAD_COLOR),self.matrice2, None)
    
    def callback_cmd(self,data):
        self.consigne = data
    
    
    # Fonction principale a appeler en boucle 
    def control(self):
        """
        
        Detecte la plante  --> il faudra ajouter si rien est detecté, bouger aléatoirement  
        La place en son centre
        S'avance vers elle 
        
        Quand il est bien placé apelle la fonction pour peindre  
        
        """
        if self.arreter == 1:
            if (self.img2 is not None) and (self.consigne is not None) :
                             a,b,area = detect(self.img2)
                             print("image bras area  = ", area)
#                             while (area == False):
#                                 self.consigne.linear.x = 0
#                                 self.consigne.angular.z = 0.02
#                                 self.pub.publish(self.consigne)
#                                 a,b,area = detect(self.img2)
#                                 print("tourner g")
                                 
                                 
                             if a!=False:
                                 [l,L,_] = self.img2.shape
                                 self.cx,self.cy = a,b
                                 #initial arm position
                                 x0 = np.round(l/2)
                                 y0 = np.round(L/2)
                                 L20 = 0
                                 
                                 #desired position
                                 xd = self.cx
                                 yd = self.cy
                                 print("x sit = ",x0,xd)
                                 print("y sit = ",y0,yd)
                                 #calculate next theta value
                                 thetad = setTheta(xd,yd,x0,y0)
                                 self.publisher_angle.publish(thetad)    
                                 #calculate next L value
                                 L2_fin,x0_laser,y0_laser = setL(L20,thetad,x0,y0,xd,yd)
                                 self.publisher_L.publish(L2_fin)  
                                 #calculate finaL laser position
                                 x_laser = x0 + (0.4 + L2_fin)*np.cos(thetad) 
                                 y_laser = y0 + (0.4 + L2_fin)*np.sin(thetad)
    

                                 print ("thetad = ",thetad)
                                 print ("L2 = ",L2_fin)
                                 print (x_laser,y_laser)


        if (self.img1 is not None) and (self.consigne is not None) and self.arreter == 0 :
            a,b,_ = detect(self.img1)
            print("image")
            if a!=False:

                self.cx,self.cy = a,b
                self.angle, self.hauteur = getAngle(self.img1,self.cx,self.cy)
                # Regler angle
                
                if self.angle >= ANGLE_MAX or self.angle <= ANGLE_MIN :                  
                    while self.angle >= ANGLE_MAX or self.angle <= ANGLE_MIN :
                        print("je suis dans le while je regle l'angle")
                        self.consigne.linear.x = 0
                        a,b,_ = detect(self.img1)
                        self.cx,self.cy = a,b
                        self.angle, self.hauteur = getAngle(self.img1,self.cx,self.cy)
                        print("La consigne est de ",-self.consigne.angular.z)
                        print("erreur", self.angle)
                        self.consigne.angular.z = -self.pidangle(self.angle)
                        self.pub.publish(self.consigne)
                        
                else :
                    print("HAUTEUR =" , self.hauteur)
                    self.consigne.angular.z = 0
                    # regle distance
                    if self.hauteur >= HAUTEUR + EPSILON_HAUTEUR:

                        #avance
                        self.consigne.linear.x = -0.1
                        self.pub.publish(self.consigne)
                        print("recule")
                    elif self.hauteur <= HAUTEUR - EPSILON_HAUTEUR:
                        print("avance")
                        self.consigne.linear.x = 0.1
                        self.pub.publish(self.consigne)
                    else:
                        print("arrete toi!!!!")
                        self.arreter = 1
                        #self.consigne.linear.x = -self.consigne.linear.x
                        self.consigne.angular.z = 0
                        self.consigne.linear.x = 0
                        self.pub.publish(self.consigne)
                         # quand fini peindre mettre à false
                        #peindre
                                        
            else : # On ne detecte pas de plante, il fausdra bouger aléatoirement
                print("Je cherche une plante")
                self.consigne.angular.z = 0.05
                self.pub.publish(self.consigne)
                
        else :
              print('### Pas d image ####')
                  

		
def main():
	rospy.init_node('deplacement_avec_pid', anonymous=False)
	data = data_getting()
	rate = rospy.Rate(4)
	
	while not rospy.is_shutdown() :
		data.control()
		rate.sleep()	
		
	
	
if __name__ == '__main__':
	main()
				

	
