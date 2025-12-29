from django.http import JsonResponse
from FYP_APP.models import New_Stock_Data


def stock_data_from_api(symbol):
    """
    Fetch stock data from Finnhub API and return JSON.
    This function can be called directly from urls.py.
    """
    import requests
    import datetime,pytz
    from django.conf import settings

    try:
        # Call Finnhub API
        response = requests.get("https://finnhub.io/api/v1/quote",params={"symbol": symbol, "token": settings.FINNHUB_API_KEY})
        response.raise_for_status()
        data = response.json()
        print(data)
        if data and data.get('t'):
            timestamp = data['t']
            # converting Unix timestamp to date
            utc_dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
            nepal_dt = utc_dt.astimezone(pytz.timezone("Asia/Kathmandu"))
            if  not New_Stock_Data.objects.filter(symbol=symbol , nepal_dt=nepal_dt.date()).exists():
                stock = New_Stock_Data.objects.create(
                    symbol = symbol,
                    utc_dt = utc_dt.date(),
                    nepal_dt = nepal_dt.date(),
                    open_price=data['o'],
                    high_price=data['h'],
                    low_price=data['l'],
                    close_price=data['c'],
                    change=data['d'],
                    volume = 0,
                    change_percent=f"{data['dp']*100:.2f}%"
                    )
                stock.save()
                # Print to terminal
                print(f"new data of Stock with different symbol or date for {symbol}: {data}")    
            else:
                print("Data already exist in database")
        else:
            print("No valid data from API")
            return None
        return (nepal_dt.date())
    except requests.RequestException as e:
        print(f"Error fetching stock data: {e}")
        return None
    
def stock_data_from_database(nepal_dt,symbol):
    """
    Fetch stock data from database and return JSON.
    This function can be called directly from urls.py.
    """
    stock_data = (
        New_Stock_Data.objects.filter(symbol=symbol, nepal_dt=nepal_dt).order_by("-nepal_dt").first()
    )
           
    if stock_data:
        print("Data exist")
        return ({
            "symbol": stock_data.symbol,
            "date": stock_data.nepal_dt,
            "open": stock_data.open_price,
            "high": stock_data.high_price,
            "low": stock_data.low_price,
            "close": stock_data.close_price,
            "change": stock_data.change,
            "change_percent": stock_data.change_percent,
            "source": "database"
        })
    return None

    
    




