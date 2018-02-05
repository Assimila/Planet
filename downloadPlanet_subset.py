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
      1 - It is neccesary first to create an account. Set the user login 
          details in YOUR_EMAIL and YOUR_PASSWD strings within the script
      2 - Get the API key at planet.com/account/
          Store the key as en environmental variable, e.g. in .bashrc
          export PL_API_KEY=a3a64774d30c4749826b6be445489d3b # (not a real key)
      3 - Install the Planet API, see:
          https://github.com/planetlabs/planet-client-python

    - To run the script and get data (2 images):
      python downloadPlanet.py

      To download more than 2 images, modify the NumberOfImages variable 

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
    item_id, item_type = item_info.split(' ', 2)
    stdout.write("attempting to obtain "+item_id+item_type)

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
        # until you see a URL in the 'location' element of the response.
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
    asset_location_url = item_to_download.json()[asset_type]['location']

    # Subset
    vsicurl_url = '/vsicurl/' + asset_location_url
    output_file = item_id + '_subarea.tif'

    # GDAL Warp crops the image by our AOI, and saves it
    subset_fname = 'subset.geojson'
    gdal.Warp(output_file, vsicurl_url, dstSRS='EPSG:4326',
               cutlineDSName=subset_fname, cropToCutline=True)

# ========================================================================== #

# GeoJSON AOI
# e.g. http://geojson.io
# Reads the subset.geojson file within the planet directory
with open("subset.geojson") as f:
    geoj = json.load(f)

aoi = {
     "type": geoj['features'][0]['geometry']['type'],
     "coordinates": geoj['features'][0]['geometry']['coordinates']
}

# Get API key
api_key = api.ClientV1().login('lopez.saldana@gmail.com', 'gertan20')

# Create client
client = api.ClientV1(api_key=api_key['api_key'])

# Build a query using the AOI and a cloud_cover filter
# that get images with lower than 10% cloud cover
# and acquired on Nov 1st, 2017
query = filters.and_filter(
    filters.geom_filter(aoi),
    filters.range_filter('cloud_cover', lt=0.1),
    filters.date_range('acquired',
                        gte='2017-03-01T00:00:00.000Z',
                        lte='2017-03-05T23:59:00.000Z')
)

# Build a request for only PlanetScope imagery
# Item types:
#   https://www.planet.com/docs/reference/data-api/items-assets
request = filters.build_search_request(
    query, item_types=['PSScene4Band'])

# Get results
result = client.quick_search(request)

# Setup auth
session = requests.Session()
session.auth = (api_key['api_key'], '')

# Set asset type to download
asset_type = 'analytic'

stdout.write('item_id,  item_type,  cloud_cover,  date\n')

# Set a limit for the maximum number of results to download from the API
# that have been returned from the API request.
NumberOfImages = 200

# Loop over each item found during the request and append the info
# to an image_ids text file so that it can be passed to the ThreadPool
# to parallel-ize the requests.
#
# Also, save the metadata of each file to a text file with the filename
# set to the image_id.
with open("image_ids.txt", 'w') as id_file:

    # items_iter returns a limited iterator of all results,
    # behind the scenes, the client is paging responses from the API
    for item in result.items_iter(limit=NumberOfImages):
        props = item['properties']
        item_id = item['id']
        item_type = item['properties']['item_type']

        stdout.write('{0}  ,{item_type},  {cloud_cover},  '
                     '{acquired}\n'.format(item['id'], **props))

        # Update T. Day 05/02/2018
        # Save property dictionary to txt file to
        # obtain and save angular information from metadata
        # as gdal.Warp removes this information.

        with open(str(item_id)+".txt", 'w') as metadata_file:
            metadata_file.write(json.dumps(props))

        # Append each item_id to a text file to support parallelism
        id_file.write(item_id+" "+item_type+"\n")

# Reopen the image_id text file in read mode to
# pass to the activate_item
with open("image_ids.txt", 'r') as id_file:
    item_info = id_file.read().splitlines()[:]

    # Set up the parallelism so that 5 requests can run simultaneously
    parallelism = 5
    thread_pool = ThreadPool(parallelism)

    # All items will be sent to the 'activate_item' function but only
    # 5 will be run at once
    thread_pool.map(activate_item, item_info)

# ================================================================= #


#     # Request an item
#     item_to_download = \
#         session.get(
#         ("https://api.planet.com/data/v1/item-types/" +
#         "{}/items/{}/assets/").format(item_type, item_id))
#
#     # Extract the activation url from the item for the desired asset
#     item_activation_url = item_to_download.json()[
#                           asset_type]["_links"]["activate"]
#
#     # Request activation
#     response = session.post(item_activation_url)
#
#     # HTTP 204: Success, No Content to show
#     while response.status_code <> 204:
#         print "Response code:", response.status_code
#         print "Waiting for activation code..."
#         # Activation will take ~8 minutes. Run the command above again
#         # until you see a URL in the 'location' element of the response.
#         time.sleep( 9 * 60 )
#         # Request an item
#         item_to_download = \
#             session.get(
#                 ("https://api.planet.com/data/v1/item-types/" +
#                  "{}/items/{}/assets/").format(item_type, item_id))
#
#         # Extract the activation url from the item for the desired asset
#         item_activation_url = item_to_download.json()[
#                                   asset_type]["_links"]["activate"]
#
#         # Request activation once again...
#         response = session.post(item_activation_url)
#
#     # Get location of the asset
#     asset_location_url = item_to_download.json()[asset_type]['location']
#
#     # Subset
#     vsicurl_url = '/vsicurl/' + asset_location_url
#     output_file = item_id + '_subarea.tif'
#
    # Update T. Day 05/02/2018
    # Save property dictionary to txt file to
    # obtain and save angular information from metadata
    # as gdal.Warp removes this information.

    #with open(str(item_id) + ".txt", 'w') as file:
    #    file.write(json.dumps(props))
#
#     # GDAL Warp crops the image by our AOI, and saves it
#     subset_fname = 'subset.geojson'
#     gdal.Warp( output_file, vsicurl_url, dstSRS = 'EPSG:4326',
#                cutlineDSName = subset_fname, cropToCutline = True )

