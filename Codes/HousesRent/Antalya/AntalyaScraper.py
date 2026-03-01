import asyncio
import random
from camoufox.async_api import AsyncCamoufox
import csv
import datetime

BASE_URL = "https://www.sahibinden.com/kiralik/antalya"
MAX_PAGES = 650
BATCH_SIZE = 50
month = datetime.datetime.now().month
day = datetime.datetime.now().day
USER_DATA_DIR = "./camoufox_profile"
is_first_run = True
async def scrape_page(page, page_num):

    offset = (page_num - 1) * 20
    url = f"{BASE_URL}?pagingOffset={offset}"

    await page.goto(url, timeout=60000)
    await page.wait_for_selector("tr.searchResultsItem", timeout=15000)


    await page.mouse.move(
        random.randint(100, 800),
        random.randint(100, 600),
        steps=random.randint(10, 20)
    )

    await asyncio.sleep(random.uniform(1, 3))

    listings = await page.query_selector_all("tr.searchResultsItem")
    page_data = []
    for item in listings:
        try:
            title_elem = await item.query_selector(".classifiedTitle")
            title = await title_elem.inner_text() if title_elem else "N/A"
            title = title.strip()

            price_elem = await item.query_selector(".classified-price-container")
            price = await price_elem.inner_text() if price_elem else "N/A"
            price = price.strip()

            location_elem = await item.query_selector(".searchResultsLocationValue")
            location = await location_elem.inner_text() if location_elem else "N/A"
            location = location.strip()
            location = location.replace("\n", "/")

            attr_elems = await item.query_selector_all(".searchResultsAttributeValue")
            room = "N/A"
            for elem in attr_elems:
                text = await elem.inner_text()
                if "+" in text.lower():
                    room = text.strip()
                    break
            page_data.append([title, price, location,room])
        except Exception as e:
            print(f"Error: {e}")
            continue

    return page_data


async def process_batch(start_page, end_page,isFirst):

    all_data = []


    async with AsyncCamoufox(
            os="windows",
            humanize=True,
            locale="tr-TR",
            headless=not isFirst,
            persistent_context=True,
            user_data_dir=USER_DATA_DIR,
            geoip=True,
    ) as fox:
        page = await fox.new_page()

        for page_num in range(start_page, end_page + 1):


            await asyncio.sleep(random.uniform(3, 8))

            data = await scrape_page(page, page_num)
            if not data:

                break
            all_data.extend(data)

    return all_data


async def main():
    all_results = []


    for batch_start in range(1, MAX_PAGES + 1, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE - 1, MAX_PAGES)

        if batch_start == 1:
            is_first_run = True
        else:
            is_first_run = False

        batch_data = await process_batch(batch_start, batch_end,is_first_run)
        all_results.extend(batch_data)



        await asyncio.sleep(random.uniform(10, 20))


        with open(f"batch_{batch_start}_{batch_end}_date_{month}-{day}.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Price", "Location", "Number of Rooms"])
            writer.writerows(batch_data)



if __name__ == "__main__":
    asyncio.run(main())
