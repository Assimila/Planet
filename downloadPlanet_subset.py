# coding=utf-8
"""
Purpose
  The downloadPlanet script:
    - Download free Planet data using their API for the area of
      interest (aoi) specified as a bounding box in Lat/Lon in
      GeoJSON format -- see aoi variable --
      The script only gets the PlanetScope OrthoTiles (PSOrthoTile)
      and the RapidEye OrthoTiles (REOrthoTile) but different Planet
      ItemTypes could be donwloaded:
      https://www.planet.com/docs/reference/data-api/items-assets/#item-type

      Compulsory steps before running the script:      
      1 - It is necessary first to create an account. Set the user login
          details in YOUR_EMAIL and YOUR_PASSWD strings within the script
      2 - Get the API key at planet.com/account/
          Store the key as en environmental variable, e.g. in .bashrc
          export PL_API_KEY=a3a64774d30c4749826b6be445489d3b # (not a real key)
      3 - Install the Planet API, see:
          https://github.com/planetlabs/planet-client-python

    - To run the script and get data (2 images):
      python downloadPlanet.py

      To download more than 2 images, modify the json "max_num_to_download" variable

"""

__author__ = "Gerardo López Saldaña"
__version__ = "0.2 (20.10.2017)"
__email__ = "gerardo.lopezsaldana@assimila.eu"

import os
import requests
import time
import osgeo.gdal as gdal
import json
from multiprocessing.dummy import Pool as ThreadPool

from planet import api
from planet.api import filters
from sys import stdout

def activate_item(item_info):

    """
    This is the main method that activates and downloads the API
    request. It is set up to handle parallelism so that multiple
    requests can be handled at once using ThreadPool.

    :param item_info: This is the line of the item_info text file
                      which details the item_id and item_type.

    :return: N/A
    """

    # Strip out the item_type and item_id from item_info
    item_id, item_type = item_info.split(" ", 2)
    stdout.write("attempting to obtain "+item_id+item_type+"\n")

    # Request an item
    item_to_download = \
        session.get(
        ("https://api.planet.com/data/v1/item-types/" +
        "{}/items/{}/assets/").format(item_type, item_id))

    # Extract the activation url from the item for the desired asset
    item_activation_url = item_to_download.json()[
                          asset_type]["_links"]["activate"]

    # Request activation
    response = session.post(item_activation_url)

    # HTTP 204: Success, No Content to show
    while response.status_code <> 204:
        print "Response code:", response.status_code
        print "Waiting for activation code..."
        # Activation will take ~8 minutes. Run the command above again
        # until you see a URL in the "location" element of the response.
        time.sleep(9*60)
        # Request an item
        item_to_download = \
            session.get(
                ("https://api.planet.com/data/v1/item-types/" +
                 "{}/items/{}/assets/").format(item_type, item_id))

        # Extract the activation url from the item for the desired asset
        item_activation_url = item_to_download.json()[
                                  asset_type]["_links"]["activate"]

        # Request activation once again...
        response = session.post(item_activation_url)

    # Get location of the asset
    asset_location_url = item_to_download.json()[asset_type]["location"]

    # Subset
    vsicurl_url = "/vsicurl/" + asset_location_url
    output_file = "images/" + item_id + "_subarea.tif"

    # GDAL Warp crops the image by our AOI, and saves it
    subset_fname = "subset.geojson"
    gdal.Warp(output_file, vsicurl_url, dstSRS="EPSG:4326",
               cutlineDSName=subset_fname, cropToCutline=True)

# ========================================================================== #

# GeoJSON AOI
# e.g. http://geojson.io
# Reads the subset.geojson file within the planet directory and
# sets the aoi variable required by the download script.
with open("subset.geojson") as f:
    geoj = json.load(f)

aoi = {
     "type": geoj["features"][0]["geometry"]["type"],
     "coordinates": geoj["features"][0]["geometry"]["coordinates"]
}

# Read the configuration json file and extract variables to be used
# in the script.
with open("configuration.json") as f:
    conf = json.load(f)

    login_email = conf[0]["login_email"]
    passwd = conf[0]["pw"]
    acceptable_cloud_cover = conf[0]["acceptable_cloud_cover"]
    start_date = conf[0]["start_date"]
    end_date = conf[0]["end_date"]
    item_type_name = conf[0]["item_type_name"]
    asset_type = conf[0]["asset_type"]

    # Set a limit for the maximum number of results to download from the API
    # that have been returned from the API request.
    max_download = conf[0]["max_num_to_download"]

# Get API key
api_key = api.ClientV1().login(login_email, passwd)

# Create client
client = api.ClientV1(api_key=api_key["api_key"])

# Build a query using the AOI and a cloud_cover filter
# that get images with lower than 10% cloud cover
# and acquired on Nov 1st, 2017
query = filters.and_filter(
    filters.geom_filter(aoi),
    filters.range_filter("cloud_cover", lt=acceptable_cloud_cover),
    filters.date_range("acquired",
                       gte=start_date,
                       lte=end_date)
)

# Build a request for only PlanetScope imagery
# Item types:
#   https://www.planet.com/docs/reference/data-api/items-assets
request = filters.build_search_request(
    query, item_types=[item_type_name])

# Get results
result = client.quick_search(request)

# Setup auth
session = requests.Session()
session.auth = (api_key["api_key"], "")

stdout.write("item_id,  item_type,  cloud_cover,  date\n")

# Loop over each item found during the search request and append the info
# to an image_ids text file so that it can be passed to the ThreadPool
# to parallel-ize the requests.
#
# Also, save the metadata of each file to a text file for each image_id.
with open("id_list/image_ids.txt", "w") as id_file:

    # items_iter returns a limited iterator of all results,
    # behind the scenes, the client is paging responses from the API
    for item in result.items_iter(limit=max_download):
        props = item["properties"]
        item_id = item["id"]
        item_type = item["properties"]["item_type"]

        stdout.write("{0}  ,{item_type},  {cloud_cover},  "
                     "{acquired}\n".format(item["id"], **props))

        # Update T. Day 05/02/2018
        # Save property dictionary to txt file to
        # obtain and save angular information from metadata
        # as gdal.Warp removes this information.

        with open("metadata/"+str(item_id)+".txt", "w") as metadata_file:
            metadata_file.write(json.dumps(props))

        # Append each item_id to a text file to support parallelism
        id_file.write(item_id+" "+item_type+"\n")

# Reopen the image_id text file in read mode to
# pass to the activate_item
with open("id_list/image_ids.txt", "r") as id_file:
    item_info = id_file.read().splitlines()[:]

    # Set up the parallelism so that 5 requests can run simultaneously
    parallelism = 5
    thread_pool = ThreadPool(parallelism)

    # All items will be sent to the "activate_item" function but only
    # 5 will be run at once
    thread_pool.map(activate_item, item_info)

# ================================================================= #
