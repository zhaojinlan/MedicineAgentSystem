from neo4j import GraphDatabase
uri, user, pwd = "bolt://localhost:7687", "neo4j", "test1234"
try:
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:
        info = driver.get_server_info()
        print("✅ Bolt 连接成功")
        print("  地址:", info.address)
        print("  版本:", info.agent)
        # 再顺手查个节点
        cnt = s.run("MATCH (n) RETURN count(n) as c").single()['c']
        print("  当前总节点数:", cnt)
except Exception as e:
    print("❌ Bolt 连接失败:", e)
finally:
    driver.close()