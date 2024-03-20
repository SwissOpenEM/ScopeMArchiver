import time

num = 0
t0 = time.time()
for i in range(10**8):
    num = num + 1
t1 = time.time()
print(t1 - t0)
