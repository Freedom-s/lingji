import re


cnt = 0
of = open('/Users/suojianhua/PyProjects/ragflow-plus/rag/res/huqie.txt', "r", encoding="utf-8")
def key_(line):
    return str(line.lower().encode("utf-8"))[2:-1]


while True:
    if cnt == 2:
        break
    line = of.readline()
    print(line)
    line = re.sub(r"[\r\n]+", "", line)
    print(line)
    line = re.split(r"[ \t]", line)
    print(line)
    k = key_(line[0])
    print(k)
    print('--------')
    cnt += 1