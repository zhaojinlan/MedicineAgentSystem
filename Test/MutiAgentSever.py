from asyncio import streams
import configparser
from optparse import Values
from pydantic import config
from  MutiAgent  import graph

import random 

config={
    "configurable":{
        "thread_id":random.randint(1,10000)
    }
}

query="请给我讲一个郭德纲的笑话"

res=graph.invoke({"messages":["给我讲一个笑话"]}
    ,config
    ,stream_mode="values")
print(res["messages"][-1].content)