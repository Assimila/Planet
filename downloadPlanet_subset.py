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

from planet import api
from planet.api import filters
from sys import stdout

# GeoJSON AOI
# e.g. http://geojson.io
aoi = {
  "type": "Polygon",
  "coordinates": [
    [
      [-122.45593070983887, 37.76060492968732],
      [-122.41996765136719, 37.76060492968732],
      [-122.41996765136719, 37.80184969073113],
      [-122.45593070983887, 37.80184969073113],
      [-122.45593070983887, 37.76060492968732]
    ]
  ]
}

# Get API key
api_key = api.ClientV1().login( 'lopez.saldana@gmail.com', 'gertan20' )

# Create client
client = api.ClientV1( api_key = api_key['api_key'] )

# Build a query using the AOI and a cloud_cover filter
# that get images with lower than 10% cloud cover
# and acquired before Nov 1st, 2017
query = filters.and_filter(
    filters.geom_filter( aoi ),
    filters.range_filter( 'cloud_cover', lt = 0.1 ),
    filters.date_range( 'acquired', lte = '2017-11-01T00:00:00.000Z' )
)

# Build a request for only PlanetScope imagery
request = filters.build_search_request(
    #query, item_types = [ 'PSOrthoTile', 'REOrthoTile' ]
    query, item_types = [ 'PSOrthoTile' ]
)

# Get results
result = client.quick_search(request)

# Setup auth
session = requests.Session()
session.auth = ( api_key['api_key'], '')

# Set asset type to download
asset_type = 'analytic'

stdout.write('item_id,item_type,cloud_cover,date\n')

# items_iter returns a limited iterator of all results,
# behind the scenes, the client is paging responses from the API
NumberOfImages = 20
for item in result.items_iter( limit = NumberOfImages ):
    props = item['properties']
    item_id = item['id']
    item_type = item['properties']['item_type']

    stdout.write('{0},{item_type},{cloud_cover},' \
                 '{acquired}\n'.format(item['id'], **props))

    # Request an item
    item_to_download = \
        session.get(
        ("https://api.planet.com/data/v1/item-types/" +
        "{}/items/{}/assets/").format(item_type, item_id))

    # Extract the activation url from the item for the desired asset
    item_activation_url = item_to_download.json()[
                          asset_type]["_links"]["activate"]

    # Request activation
    response = session.post( item_activation_url )

    # HTTP 204: Success, No Content to show
    while response.status_code <> 204:
        print "Response code:", response.status_code
        print "Waiting for activation code..."
        # Activation will take ~8 minutes. Run the command above again
        # until you see a URL in the 'location' element of the response.
        time.sleep( 9 * 60 )
        # Request an item
        item_to_download = \
            session.get(
                ("https://api.planet.com/data/v1/item-types/" +
                 "{}/items/{}/assets/").format(item_type, item_id))

        # Extract the activation url from the item for the desired asset
        item_activation_url = item_to_download.json()[
                                  asset_type]["_links"]["activate"]

        # Request activation once again...
        response = session.post( item_activation_url )

    # Get location of the asset
    asset_location_url = item_to_download.json()[asset_type]['location']

    # Subset
    vsicurl_url = '/vsicurl/' + asset_location_url
    output_file = item_id + '_subarea.tif'

    # GDAL Warp crops the image by our AOI, and saves it
    gdal.Warp( output_file, vsicurl_url, dstSRS = 'EPSG:4326', 
               cutlineDSName = 'subset.geojson', cropToCutline = True )

