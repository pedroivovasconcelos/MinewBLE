import json, boto3, time
from boto3.dynamodb.conditions import Key, Attr

dynamodb_client = boto3.resource('dynamodb')

#Do tipo int8 faz a conversão de hexadecimal para decimal
def hexint2(var):
    var1 = int(var,16)
    if(int(var,16)>127):
        var1=int(var,16)-256
    return var1

#Gravar o log do gateway e de seus dispositivos próximos
def write_device_log(event):
    #Atrivui a tabela dos logs dos dispositivos
    table_device = dynamodb_client.Table('device_log')
    for device in event:
        sum_g = None
        try:
            #verifica se o dispositivo é o crachá C7, para cada dispositivo diferente um código específico 
            if device['rawData'] and device['rawData'][22:26] == 'A103':
                #timestamp da hora recebida com milisegundos
                time_currrently = (time.time()-10800)
                time_ms_only = round((time_currrently - int(time_currrently))*1000)
                timestamp_received = (str(time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(int(time_currrently))))+
                ".{}".format(str(time_ms_only)))
                
                mac = device['mac']
                timestamp = device['timestamp']
                rssi = device['rssi']
                battery = hexint2(device['rawData'][26:28]) #número inteiro de base hexadecimal
                x=hexint2(device['rawData'][28:30])+int(device['rawData'][30:32],16)/256
                y=hexint2(device['rawData'][32:34])+int(device['rawData'][34:36],16)/256
                z=hexint2(device['rawData'][36:38])+int(device['rawData'][38:40],16)/256
                sum_g=round(x+y+z,3)
                resultant_vector = sqrt(x^2+y^2+z^2)
                
                #grava no log dados recebidos do roteador
                table_device.put_item(Item={"raw_time_ms" : round(time_currrently*1000), "received_time" : timestamp_received, 
                "timestamp" : json.dumps(timestamp), "mac" : mac, "sum" : json.dumps(sum_g), "x" : json.dumps(round(x,3)), 
                "y" : json.dumps(round(y,3)), "z" : json.dumps(round(z,3)), "rssi" : json.dumps(rssi), 
                "battery" : json.dumps(battery), "resultant" : resultant_vector})
                
                #aviso de queda
                if (resultant_vector<0.5):
                    table_fall = dynamodb_client.Table('fall_log')
                    table_fall.put_item(Item={"timestamp" : timestamp_received,"mac" : mac, "sum" : json.dumps(sum_g), 
                    "x" : json.dumps(round(x,3)), "y" : json.dumps(round(y,3)), "z" : json.dumps(round(z,3)), 
                    "rssi" : json.dumps(rssi)})
        except KeyError:
            pass
    return

#Se o dispositivo não foi detectado recentemente, muda seu estado para fora do ar
def out_of_range(event):
    table_device = dynamodb_client.Table('device_status')
    
    for device in event:
        try:
            if device['rawData'] and device['rawData'][22:26] == 'A103':
                battery = hexint2(device['rawData'][26:28]) #base hexadecimal
                table_device.put_item(Item={"mac" : json.dumps(device['mac']), "timestamp" : json.dumps(device['timestamp']), 
                "rssi" : json.dumps(device['rssi']), "battery" : json.dumps(battery), "status" : json.dumps("online"), "counter" : json.dumps(10)})
            else:
                filtering_exp = Key('mac').eq(device['mac'])
                counter = json.loads(table_device.query(KeyConditionExpression=filtering_exp)['Items'][0]["counter"])
                if counter == 0:
                    battery = hexint2(device['rawData'][26:28]) #base hexadecimal
                    table_device.put_item(Item={"mac" : json.dumps(device['mac']), "timestamp" : json.dumps(device['timestamp']), 
                    "rssi" : json.dumps(device['rssi']), "battery" : json.dumps(battery), "status" : json.dumps("offline"), "counter" : json.dumps(0)})
                else:
                    counter=counter-1
                    battery = hexint2(device['rawData'][26:28]) #base hexadecimal
                    table_device.put_item(Item={"mac" : json.dumps(device['mac']), "timestamp" : json.dumps(device['timestamp']), 
                    "rssi" : json.dumps(device['rssi']), "battery" : json.dumps(battery), "status" : json.dumps("offline"), "counter" : json.dumps(0)})
                    
        except KeyError:
            pass
                    
    return

#função principal
def lambda_handler(event, context):
    
    #As funções devem ser alternadas a fim de não exceder o limite do AWS de gravação e leitura
    write_device_log(event)
    #out_of_range(event)
            
    return {
        'statusCode': 200,
    }
