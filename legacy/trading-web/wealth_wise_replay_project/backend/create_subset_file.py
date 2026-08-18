import copy
from datetime import datetime, timedelta

from backend import utility
from backend.utility import Utility


def get_monday_and_friday(given_date):
    # Parse the given date
    date_obj = datetime.strptime(given_date, "%Y-%m-%d")

    # Calculate Monday (weekday() gives 0 for Monday and 6 for Sunday)
    monday = date_obj - timedelta(days=date_obj.weekday())

    # Calculate Friday (weekday() gives 0 for Monday and 6 for Sunday)
    friday = monday + timedelta(days=4)

    return monday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d")

utility_temp = Utility()
df_main = utility_temp.load_historical_data("C:\Data\ES_FULL.csv")
given_date = '2024-02-02'
start_date, end_date = get_monday_and_friday(given_date)
start_time = start_date + ' 00:01:00'
end_time = end_date + ' 16:59:00'
df = df_main.loc[start_time:end_time]
df.to_csv(f'ES_SUB_SET.csv', index=True)

