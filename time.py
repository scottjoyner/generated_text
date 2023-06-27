import datetime

current_time = datetime.datetime.now().time()
current_time_ms = (current_time.hour * 3600 + current_time.minute * 60 + current_time.second) * 1000 + current_time.microsecond / 1000

target_time = datetime.time(10, 0, 0)
target_time_ms = (target_time.hour * 3600 + target_time.minute * 60 + target_time.second) * 1000

if current_time_ms > target_time_ms:
    print("The current time is after 10 AM.")
else:
    print("The current time is on or before 10 AM.")
