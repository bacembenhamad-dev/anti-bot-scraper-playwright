# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ProperstarItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    location = scrapy.Field()
    price = scrapy.Field()
    size = scrapy.Field()
    rooms = scrapy.Field()
    bedrooms = scrapy.Field()
    bathrooms = scrapy.Field()
    house_maker_contact = scrapy.Field()
