from fastapi import APIRouter, HTTPException
from ..function.mqtt_function_backend import MQTTFunctionBackend

router = APIRouter()
mqttbackend = MQTTFunctionBackend()
# Endpoint to open the door
@router.post("/open-door")
async def open_door():
    try:
        result = mqttbackend.send_unlock_command()
        if result:
            print(f"[/open-door] Door unlock command sent successfully")
            return {"message": "Door open command sent", "status": "success"}
        else:
            print(f"[/open-door] Failed to send unlock command")
            raise HTTPException(status_code=500, detail="Failed to send unlock command")
    except Exception as e:
        print(f"[/open-door] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send open command: {str(e)}")

@router.post("/change-password")
async def change_password(new_password: str):
    try:
        result = mqttbackend.change_passowrd(new_password)
        if result:
            print(f"[/change-password] Password change command sent successfully")
            return {"message": "Password change command sent", "status": "success"}
        else:
            print(f"[/change-password] Failed to send password change command")
            raise HTTPException(status_code=500, detail="Failed to send password change command")
    except Exception as e:
        print(f"[/change-password] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")


