#!/usr/bin/env python
# -*- coding: utf-8 -*-

import boto3
import json
import logging

logging.basicConfig(level=logging.INFO)

#  Amazon Web Services Price List Service API provides the following two endpoints:
#
#  https://api.pricing.us-east-1.amazonaws.com
#  https://api.pricing.ap-south-1.amazonaws.com
#
# So in the case of price we must specify us-east-1 or ap-east-1.
# This region has nothing to do with the region for the service we are looking for.
PRICING = boto3.client('pricing', region_name='us-east-1')


class Filters():
    """A simple filter builder"""

    def __init__(self):
        self._fields = []

    def add_field(self, name=None, value=None, type_='TERM_MATCH'):
        field = {"Field": name, "Value": value, "Type": type_}
        self._fields.append(field)

    def itens(self):
        return self._fields

    def __str__(self):
        return str(self._fields)

# List of Attributes for the Amazon RDS Resource
#
#  {
#    "ServiceCode": "AmazonRDS",
#    "AttributeNames": [
#      "productFamily",
#      "volumeType",
#      "deploymentModel",
#      "engineCode",
#      "enhancedNetworkingSupported",
#      "memory",
#      "dedicatedEbsThroughput",
#      "vcpu",
#      "OfferingClass",
#      "termType",
#      "locationType",
#      "storage",
#      "instanceFamily",
#      "storageMedia",
#      "databaseEdition",
#      "regionCode",
#      "acu",
#      "physicalProcessor",
#      "LeaseContractLength",
#      "clockSpeed",
#      "networkPerformance",
#      "deploymentOption",
#      "servicename",
#      "PurchaseOption",
#      "minVolumeSize",
#      "group",
#      "instanceTypeFamily",
#      "instanceType",
#      "usagetype",
#      "normalizationSizeFactor",
#      "maxVolumeSize",
#      "engineMediaType",
#      "databaseEngine",
#      "processorFeatures",
#      "Restriction",
#      "servicecode",
#      "groupDescription",
#      "licenseModel",
#      "currentGeneration",
#      "volumeName",
#      "location",
#      "processorArchitecture",
#      "operation"
#    ]
#  }
def get_rds_service_metadata(client):
    """Returns the metadata information available to the RDS service"""
    response = client.describe_services(
        FormatVersion='aws_v1',
        MaxResults=1,
        ServiceCode='AmazonRDS',
    )
    return response['Services']


def list_regions():
    """The only service that informs the different regions is EC2.
    Perhaps because it is the common service to all of them."""
    ec2 = boto3.client('ec2')
    response = ec2.describe_regions()
    regions = response['Regions']
    return regions


def get_region_long_name(region=None):
    """There is no API call that returns the longName of a region.
    We use ssm to get the longName indirectly."""
    ssm = boto3.client('ssm')
    response = ssm.get_parameter(
        Name=f'/aws/service/global-infrastructure/regions/{region}/longName')
    return response['Parameter']['Value']


#  {
#    "H82A93XZEXJAE3XC.JRTCKXETXF": {
#      "priceDimensions": {
#        "H82A93XZEXJAE3XC.JRTCKXETXF.6YS6EN2CT7": {
#          "unit": "Hrs",
#          "endRange": "Inf",
#          "description": "$1.424 per RDS db.m5.4xlarge Single-AZ instance hour (or partial hour) running PostgreSQL",
#          "appliesTo": [],
#          "rateCode": "H82A93XZEXJAE3XC.JRTCKXETXF.6YS6EN2CT7",
#          "beginRange": "0",
#          "pricePerUnit": {
#            "USD": "1.4240000000"
#          }
#        }
#      },
#      "sku": "H82A93XZEXJAE3XC",
#      "effectiveDate": "2022-05-01T00:00:00Z",
#      "offerTermCode": "JRTCKXETXF",
#      "termAttributes": {}
#    }
#  }
def get_on_demand_price(instance_type,
                        database_engine,
                        region,
                        multi_az=False):
    """Returns the on-demand value based on a set of filters."""
    filters = Filters()
    filters.add_field(name='instanceType', value=instance_type)
    filters.add_field(name='databaseEngine', value=database_engine)
    filters.add_field(name='location', value=get_region_long_name(region))
    products = PRICING.get_products(ServiceCode='AmazonRDS',
                                    Filters=filters.itens())
    price_per_unit = None
    for data in products['PriceList']:
        product = json.loads(data).get('product')
        # InstanceUsage or Multi-AZUsage
        usage_type_multi_az = 'Multi-AZUsage' in product['attributes'][
            'usagetype']

        # We arrived here looking for multi AZ but at the moment we have single instance.
        # Let's skip this one!
        if multi_az and not usage_type_multi_az:
            logging.info(f'multi_az: {multi_az}, usage_type_multi_az: {usage_type_multi_az}')
            continue

        # We are looking for single instance, unfortunately what we have is multi AZ.
        # Let's skip this one!
        if not multi_az and usage_type_multi_az:
            logging.info(f'multi_az: {multi_az}, usage_type_multi_az: {usage_type_multi_az}')
            continue

        # If it were easy to filter by usagetype, the previous if's wouldn't have been necessary...
        terms = json.loads(data).get('terms').get('OnDemand')
        price_dimensions = list(terms.values())[0].get('priceDimensions')
        price_per_unit = list(price_dimensions.values())[0].get('pricePerUnit')
    return price_per_unit


EXAMPLES = [
    {
        'example-01': {
            'instance_type': 'db.m5.4xlarge',
            'database_engine': 'PostgreSQL',
            'region': 'us-east-1',
            'multi_az': False
        }
    },
    {
        'example-02': {
            'instance_type': 'db.m5.4xlarge',
            'database_engine': 'PostgreSQL',
            'region': 'sa-east-1',
            'multi_az': False
        }
    },
    {
        'example-03': {
            'instance_type': 'db.m5.4xlarge',
            'database_engine': 'PostgreSQL',
            'region': 'us-east-1',
            'multi_az': True
        }
    },
    {
        'example-04': {
            'instance_type': 'db.m5.4xlarge',
            'database_engine': 'PostgreSQL',
            'region': 'sa-east-1',
            'multi_az': True
        }
    },
]


def main():
    """Main"""
    for example in EXAMPLES:
        key = list(example.keys())[0]
        instance_type = example[key].get('instance_type')
        database_engine = example[key].get('database_engine')
        region = example[key].get('region')
        multi_az = example[key].get('multi_az', False)

        print(
            f'{key}: {instance_type}, {database_engine}, {region}, multi_az={multi_az}'
        )
        price_per_unit = get_on_demand_price(instance_type, database_engine,
                                             region, multi_az)

        print(price_per_unit)


if __name__ in '__main__':
    main()
