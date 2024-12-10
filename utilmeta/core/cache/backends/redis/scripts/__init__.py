import os

script_path = os.path.dirname(__file__)

BATCH_RETRIEVE_LUA = open(os.path.join(script_path, "batch_retrieve.lua")).read()
BATCH_EXISTS_LUA = open(os.path.join(script_path, "batch_exists.lua")).read()
BATCH_RELATES_LUA = open(os.path.join(script_path, "batch_relates.lua")).read()
BATCH_COUNT_LUA = open(os.path.join(script_path, "batch_count.lua")).read()
ALTER_AMOUNT_LUA = open(os.path.join(script_path, "alter_amount.lua")).read()
