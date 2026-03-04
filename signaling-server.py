# signaling_server.py
import asyncio
import websockets
import json
from collections import defaultdict

clients = {}                  # id -> websocket
groups = defaultdict(set)     # group_name -> set of ids
disconnect_timers = {}        # client_id -> asyncio.Task
LEAVE_GRACE_PERIOD = 15       # seconds

async def schedule_leave(client_id):
    await asyncio.sleep(LEAVE_GRACE_PERIOD)
    # Remove client from all groups and notify others
    for gname, gset in groups.items():
        if client_id in gset:
            gset.discard(client_id)
            leave_msg = json.dumps({
                "type": "leave",
                "id": client_id,
                "group": gname
            })
            for cid in gset:
                if cid in clients:
                    await clients[cid].send(leave_msg)
    disconnect_timers.pop(client_id, None)
    print(f"{client_id} removed after grace period.")

async def handler(ws):
    client_id = None
    try:
        async for message in ws:
            data = json.loads(message)

            # Register client
            if data["type"] == "register":
                client_id = data["id"]

                # Cancel any pending leave task if reconnecting
                if client_id in disconnect_timers:
                    disconnect_timers[client_id].cancel()
                    disconnect_timers.pop(client_id, None)

                clients[client_id] = ws
                print(f"Registered {client_id}")

                if "group" in data:
                    groups[data["group"]].add(client_id)

            # Join a group
            elif data["type"] == "join_group":
                client_id = data["id"]
                clients[client_id] = ws
                groups[data["group"]].add(client_id)
                print(f"{client_id} joined group {data['group']}")

            # Broadcast to group
            elif data["type"] == "pos_update":
                group = data.get("group")
                if group and group in groups:
                    for cid in groups[group]:
                        if cid != client_id and cid in clients:
                            await clients[cid].send(message)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if client_id:
            clients.pop(client_id, None)
            # schedule a leave with grace period
            if client_id in disconnect_timers:
                disconnect_timers[client_id].cancel()
            disconnect_timers[client_id] = asyncio.create_task(schedule_leave(client_id))
            print(f"{client_id} disconnected, leave scheduled in {LEAVE_GRACE_PERIOD}s")

CLEANUP_INTERVAL = 60  # seconds

async def cleanup_groups():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        removed_groups = 0
        removed_ids = 0

        for gname in list(groups.keys()):  # use list to avoid dict size change during iteration
            # Remove client IDs that no longer exist in clients
            group_set = groups[gname]
            for cid in list(group_set):
                if cid not in clients:
                    group_set.discard(cid)
                    removed_ids += 1

            # Delete empty groups
            if not group_set:
                del groups[gname]
                removed_groups += 1

        if removed_groups or removed_ids:
            print(f"🧹 Cleanup: removed {removed_ids} stale client IDs, {removed_groups} empty groups.")


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Signaling server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever

asyncio.run(main())
