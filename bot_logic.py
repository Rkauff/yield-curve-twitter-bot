# -*- coding: utf-8 -*-
"""
Created on Thu Mar 26 10:16:34 2020

@author: 16307
"""

from matplotlib import pyplot as plt
import os
import tweepy
import logging
import boto3
from botocore.exceptions import ClientError
import io
import requests
import bs4
import re
from datetime import datetime

def lambda_handler(event, context):
    print("Incoming request...")

    my_dict = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6,
               "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12}

    us_treasury_url = 'https://www.treasury.gov/resource-center/data-chart-center/interest-rates/Pages/TextView.aspx?data=yield'

    us_treasury_yields = requests.get(us_treasury_url)
    us_treasury_yields_string = bs4.BeautifulSoup(us_treasury_yields.text, 'html.parser')
    yield_curve_date = us_treasury_yields_string.select('div.updated')[0] #Date of the yield curve
    yield_curve_labels = us_treasury_yields_string.select('th')[1:11] #Treasury Security Labels
    yield_body = str(us_treasury_yields_string.select('table.t-chart'))

    #This piece is just the date formatting.
    yield_curve_date = yield_curve_date.text.replace(',', '').split() #3 in 1. 1) Extract text, 2) remove commas, and 3) split the values apart.
    date_conversion = datetime(int(yield_curve_date[3]), int(my_dict[yield_curve_date[1]]), int(yield_curve_date[2]))
    date_conversion1 = datetime.strftime(date_conversion, "%m/%d/%y")

    begin_val = yield_body.find(date_conversion1) #determines where the current date STARTS in the yield body string
    end_val = len(yield_body) #determines where the current date ENDS in the yield body string
    new_string = yield_body[begin_val:end_val] #Captures ONLY the html data for the current day

    only_yields = new_string.split("text_view_data")

    new_item = []
    x_axis = []
    y_axis = []

    for y in range(11):
        new_item.append(re.findall('\d*\.?\d+', only_yields[y]))
        y_axis.append(float(new_item[y][0]))

    y_axis.pop(0)

    for x in range(10):
        x_axis.append(yield_curve_labels[x].getText())
    
    x_axis = x_axis[:10]
    y_axis = y_axis[:10]

    aws_access_key = "your key here" #AWS
    aws_secret_key = "your secret key here" #AWS

    font = {'family': 'serif', 'color':  'blue', 'weight': 'normal', 'size': 12}

    def inversion():
        """To determine whether the yield curve is normal, flat, or inverted."""
        if y_axis[0] > y_axis[9]:
            return 'The Yield curve is inverted by ' + str(int(abs(y_axis[9] - y_axis[0]) * 100)) + ' bps.*'
        elif y_axis[0] == y_axis[9]:
            return 'The Yield curve is flat.*'
        else:
            return 'The Yield curve is normal by ' + str(int(abs(y_axis[9] - y_axis[0]) * 100)) + ' bps.*'

    plt.figure(figsize=(10, 5))
    plt.title("Yield Curve as of " + str(date_conversion1))
    plt.scatter(x_axis, y_axis, c='r', label='Treasury Securities')
    plt.plot(x_axis, y_axis, label="Yield Curve")
    plt.legend()
    plt.ylim(bottom=0, top=3)  #To set the y-axis at 0, Top at 3.
    plt.xlabel('Treasury Security', fontdict=font)
    plt.ylabel('Rate (%)', fontdict=font)
    graph_description = plt.text(0, 2.7, inversion(), bbox=dict(facecolor='yellow', alpha=0.5))
    graph_description2 = plt.text(0, 2.5, str(x_axis[0]) + " T-bill against the " + str(x_axis[9]) + " T-note", bbox=dict(facecolor='yellow', alpha=0.5))

    img_data = io.BytesIO() #Read the plot to memory, so it doesn't need to be saved down locally.
    plt.savefig(img_data, format='png') #Save it to memory
    img_data.seek(0) #Sets the file's current position at the offset

    # Create an S3 client
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key)

    try:
        s3_client.put_object(Body=img_data, Bucket='yield-curve', ContentType='image/png', Key='yield_curve')
    
    except ClientError as e:
        logging.error(e)

    CONSUMER_KEY = "your consumer key here"
    CONSUMER_SECRET = "your consumer secret key here"
    ACCESS_TOKEN = "your access token"
    ACCESS_SECRET = "your secret access token here"

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)

    # Twitter requires all requests to use OAuth for authentication
    auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
    api = tweepy.API(auth)

    user = api.me()

    status = "Yield Curve for " + str(date_conversion1)

    # Create an S3 Resource to download from the yield-curve bucket
    s3 = boto3.resource(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key)

    # download frame jpg from s3 and save to /tmp in the Lambda function itself
    s3.Bucket("yield-curve").download_file("yield_curve", "/tmp/yield_curve.png")
    
    user = api
    
    # tweet picture from /tmp location. Important to remember, this is not 
    # getting tweeted from S3 directly.
    user.update_with_media('/tmp/yield_curve.png', status)

    # delete local image
    os.remove('/tmp/yield_curve.png')
