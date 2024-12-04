import requests
from math import ceil
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger('supermarkt_connector')
logger.setLevel(logging.INFO)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/86.0.4240.75 Safari/537.36'
}


class JumboConnector:
    def search_products(self, query=None, page=0, size=None):
        if size:
            logging.info("size is unnecessary, as jumbo always returns 24 products per page")
        search_url = 'https://www.jumbo.com/producten/'
        offSet = page * 24
        query = query.replace(' ', '+') if query else ''
        params = {
            'searchType': 'keyword',
            'searchTerms': query,
            'offSet': offSet,
        }
        response = requests.get(search_url, headers=HEADERS, params=params)
        if not response.ok:
            response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract total number of products
        total_products_tag = soup.find('span', class_='results')
        total_products_text = total_products_tag.get_text(strip=True) if total_products_tag else '0 producten gevonden'
        total_products = int(''.join(filter(str.isdigit, total_products_text)))

        product_list = soup.find_all('article', class_='product-container')
        products = []
        for product_div in product_list:
            # Name
            name_tag = product_div.find('h3', class_='jum-heading')
            product_name = name_tag.get_text(strip=True) if name_tag else None

            # Link
            link_tag = name_tag.find('a', class_='title-link') if name_tag else None
            product_link = link_tag['href'] if link_tag else None

            # Price
            price_container = product_div.find('div', class_='jum-price')
            price_whole = price_container.find('span', class_='whole') if price_container else None
            price_fractional = price_container.find('span', class_='fractional') if price_container else None
            if price_whole and price_fractional:
                product_price = f"{price_whole.get_text(strip=True)}.{price_fractional.get_text(strip=True)}"
            else:
                product_price = None

            products.append({
                'name': product_name,
                'link': product_link,
                'price': product_price,
            })
        return products, total_products

    def search_all_products(self, query=None):
        page = 0
        total_products = None
        product_counter = 0

        while True:
            products, first_page = self.search_products(query=query, page=page, size=size)
            
            if total_products is None:
                total_products = first_page
                total_pages = ceil(total_products / size)

            if not products:
                break

            yield from products
            product_counter += len(products)

            if product_counter >= total_products:
                break
            
            page += 1

            if page >= total_pages:
                break

    def get_product_by_barcode(self, barcode):
        products = self.search_products(query=barcode)
        result = products[0] if products else None
        return result

    def __validate_jumbo_link(self, link):
        if not link or not link.startswith('/producten/'):
            raise ValueError('Jumbo link is required')
    
    # FIXME: Almost all of this data is contained within the search result thumbnail itself, so this method is redundant
    def get_product_details(self, product):
        product_link = product if isinstance(product, str) else product.get('link')
        self.__validate_jumbo_link(product_link)
        response = requests.get('https://www.jumbo.com' + product_link, headers=HEADERS)
        if not response.ok:
            response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        product_details = {}
        
        info_div = soup.find('div', class_='product-panel-info')
        
        # Product name
        name_tag = info_div.find('h1', class_='jum-heading')
        product_details['name'] = name_tag.text.strip() if name_tag else None

        # Description (find the first div with class 'open jum-collapsible')
        description_tag = soup.find('div', class_='open jum-collapsible')
        product_details['description'] = description_tag.text if description_tag else None

        # Price
        price_integer = info_div.find('span', class_='whole')
        price_decimal = info_div.find('span', class_='fractional')
        if price_integer and price_decimal:
            product_details['price'] = f"{price_integer.text.strip()}.{price_decimal.text.strip()}"
        else:
            product_details['price'] = None

        # Quantity
        quantity_tag = info_div.find('span', class_='product-subtitle')
        product_details['quantity'] = quantity_tag.text.strip() if quantity_tag else None
        
        # Image
        image_tag = soup.find('img', class_='image')
        product_details['image'] = image_tag['src'] if image_tag else None
        
        # PPU
        ppu_tag = info_div.find('div', class_='price-per-unit')
        if ppu_tag:
            ppu = ppu_tag.find_all('span')
            product_details['ppu'] = f"{ppu[0].text.strip()} {ppu[1].text.strip()} {ppu[2].text.strip()}"
        else:
            product_details['ppu'] = None
        
        return product_details

    def get_categories(self):
        raise NotImplementedError("Only product search is supported")
        response = requests.get(
            'https://mobileapi.jumbo.com/' + self.jumbo_api_version + '/categories',
            headers=HEADERS
        )
        if not response.ok:
            response.raise_for_status()
        return response.json()['categories']['data']

    def get_sub_categories(self, category):
        raise NotImplementedError("Only product search is supported")
        category_id = category if not isinstance(category, dict) else category['id']
        response = requests.get(
            'https://mobileapi.jumbo.com/' + self.jumbo_api_version + '/categories',
            headers=HEADERS,
            params={"id": category_id}
        )
        if not response.ok:
            response.raise_for_status()
        return response.json()['categories']['data']

    def get_all_stores(self):
        raise NotImplementedError("Only product search is supported")
        response = requests.get(
            'https://mobileapi.jumbo.com/' + self.jumbo_api_version + '/stores',
            headers=HEADERS
        )
        if not response.ok:
            response.raise_for_status()
        return response.json()['stores']['data']

    def get_store(self, store):
        raise NotImplementedError("Only product search is supported")
        store_id = store if not isinstance(store, dict) else store['id']
        response = requests.get(
            'https://mobileapi.jumbo.com/' + self.jumbo_api_version + '/stores/{}'.format(store_id),
            headers=HEADERS
        )
        if not response.ok:
            response.raise_for_status()
        return response.json()['store']['data']

    def get_all_promotions(self):
        raise NotImplementedError("Only product search is supported")
        response = requests.get(
            'https://mobileapi.jumbo.com/' + self.jumbo_api_version + '/promotion-overview',
            headers=HEADERS
        )
        if not response.ok:
            response.raise_for_status()
        return response.json()['tabs']

    def get_promotions_store(self, store):
        raise NotImplementedError("Only product search is supported")
        store_id = store if not isinstance(store, dict) else store['id']
        response = requests.get(
            'https://mobileapi.jumbo.com/' + self.jumbo_api_version + '/promotion-overview',
            headers=HEADERS,
            params={"store_id": store_id}
        )
        if not response.ok:
            response.raise_for_status()
        return response.json()['tabs']



if __name__ == '__main__':
    print("Just use pip install -e <root> to test")