import time
import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

print("Worker uruchomiony i nasłuchuje zadań...")
while True:
    time.sleep(10)
    print("Worker: Przetwarzanie zadań w tle zakończone pomyślnie.")