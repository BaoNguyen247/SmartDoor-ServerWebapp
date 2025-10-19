import paho.mqtt.client as mqtt
class MQTTFunctionBackend:
    client = mqtt.Client()

    def __init__(self):
        self.client = mqtt.Client()
        self.MQTT_BROKER = "localhost"
        self.MQTT_PORT = 1883
        self.MQTT_TOPIC_CONTROL = "door/control"
        self.MQTT_TOPIC_CHANGE_PASSWORD = "password/update"

    def send_unlock_command(self):
        try:
            self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.client.publish(self.MQTT_TOPIC_CONTROL, "unlock")
            client.disconnect()
            return True
        except Exception as e:
            print(f"[send_unlock_command] Error: {e}")
            return False
        

    def change_passowrd(self, new_password: str):
        try:
            self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.client.publish(self.MQTT_TOPIC_CHANGE_PASSWORD, new_password)
            client.disconnect()
            return True
        except Exception as e:
            print(f"[change_password] Error: {e}")
            return False
        
