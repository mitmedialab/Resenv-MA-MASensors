
import collections

import zephyr.util
import array
import bitstring


HxMMessage = collections.namedtuple("HxMMessage",
                                    ["heart_rate", "heartbeat_number", "heartbeat_milliseconds",
                                     "distance", "speed", "strides"])


SummaryMessage = collections.namedtuple("SummaryMessage",
                                            ["sequence_number", "timestamp", "heart_rate", "respiration_rate", "skin_temperature", "posture", "activity", "peak_acceleration", 
                                             "battery_volatge", "battery_level",  
                                             "respiration_wave_amplitude", "respiration_wave_noise", "respiration_wave_confidence",  
                                             "ecg_wave_amplitude", "ecg_wave_noise", "ecg_wave_confidence",
                                             "hrv", "system_confidence",
                                             "gsr", "rog", 
                                             "accl_vertical_min", "accl_vertical_peak", "accl_lateral_min", "accl_lateral_peak", "accl_sagittal_min", "accl_sagittal_peak", 
                                             "device_internal_temp", "estimated_core_temp",
                                             "posture_unreliable", "skin_temperature_unreliable", "respiration_rate_unreliable", "heart_rate_unreliable", "estimated_core_temp_unreliable", "hrv_unreliable", "activity_unreliable",
                                             "not_fitted_to_garmet", "button_pressed", "device_worn_detection_level", "resting_stage_detection",
                                             "link_quality","rssi","tx_power"
                                             ])



SignalPacket = collections.namedtuple("SignalPacket", ["type", "timestamp", "samplerate",
                                                       "samples", "sequence_number"])

AccelerationSignalSample = collections.namedtuple("AccelerationSignalSample", ["type", "timestamp", "samplerate",
                                                                               "sample_x", "sample_y", "sample_z", "sequence_number"])

SignalSample = collections.namedtuple("SignalSample", ["type", "timestamp", "samplerate",
                                                       "sample", "sequence_number"])


#Specification of HxM payload bytes:
#Firmware ID
#Firmware Version
#Hardware ID
#Hardware Version
#Battery Charge Indicator
#Heart Rate
#Heart Beat Number
#Heart Beat Timestamp #1 (Oldest)
#Heart Beat Timestamp #2
#...
#Heart Beat Timestamp #14
#Heart Beat Timestamp #15 (Oldest)
#Reserved
#Reserved
#Reserved
#Distance
#Instantaneous speed
#Strides
#Reserved
#Reserved

def parse_hxm_message(payload):
    heart_rate, heartbeat_number = payload[9:11]
    
    heartbeat_timestamp_bytes = payload[11:41]
    
    movement_data_bytes = payload[47:53]
    
    distance, speed, strides = tuple(zephyr.util.parse_uint16_values_from_bytes(movement_data_bytes))
    
    distance = distance / 16.0
    speed = speed / 256.0
    
    heartbeat_milliseconds = list(zephyr.util.parse_uint16_values_from_bytes(heartbeat_timestamp_bytes))
    
    hxm_message = HxMMessage(heart_rate=heart_rate, heartbeat_number=heartbeat_number,
                             heartbeat_milliseconds=heartbeat_milliseconds, distance=distance,
                             speed=speed, strides=strides)
    return hxm_message

def parse_summary_packet(payload):
    
    sequence_number = payload[0]    
    timestamp = zephyr.util.parse_timestamp(payload[1:9])
    
    # We are skipping a byte (index = 9) that has the version number of the packing format (should equal 2).
    remaining_payload = array.array("B",payload[10:]).tostring()
    bit_string = bitstring.ConstBitStream(bytes=remaining_payload)
    
    heart_rate = bit_string.read(16).uintle
    respiration_rate = bit_string.read(16).uintle * 0.1 
    skin_temperature = bit_string.read(16).intle * 0.1
    posture = bit_string.read(16).intle
    activity = bit_string.read(16).uintle * 0.01
    peak_acceleration = bit_string.read(16).uintle * 0.01
    
    battery_volatge = bit_string.read(16).uintle * 0.001
    battery_level = bit_string.read(8).uintle 
    
    respiration_wave_amplitude = bit_string.read(16).uintle 
    respiration_wave_noise = bit_string.read(16).uintle 
    respiration_wave_confidence = bit_string.read(8).uintle 
    
    ecg_wave_amplitude = bit_string.read(16).uintle * 0.000001 
    ecg_wave_noise = bit_string.read(16).uintle * 0.000001
    ecg_wave_confidence = bit_string.read(8).uintle

    hrv = bit_string.read(16).uintle
    system_confidence = bit_string.read(8).uintle

    gsr = bit_string.read(16).uintle
    rog = bit_string.read(16).uintle    
    
    accl_vertical_min = bit_string.read(16).intle * 0.01
    accl_vertical_peak = bit_string.read(16).intle * 0.01
    accl_lateral_min = bit_string.read(16).intle * 0.01
    accl_lateral_peak = bit_string.read(16).intle * 0.01
    accl_sagittal_min = bit_string.read(16).intle * 0.01
    accl_sagittal_peak = bit_string.read(16).intle * 0.01
    
    device_internal_temp = bit_string.read(16).intle * 0.1
    
    # This is the Status Byte.
    posture_unreliable = bit_string.read(1).bool
    skin_temperature_unreliable = bit_string.read(1).bool
    respiration_rate_unreliable = bit_string.read(1).bool
    heart_rate_unreliable = bit_string.read(1).bool
    not_fitted_to_garmet = bit_string.read(1).bool
    button_pressed = bit_string.read(1).bool
    device_worn_detection_level = bit_string.read(2).bin
    external_sensors_connected = bit_string.read(1).bool
    resting_stage_detection = bit_string.read(1).bool
    unused = bit_string.read(2)
    usb_connected_flag = bit_string.read(1).bool
    estimated_core_temp_unreliable = bit_string.read(1).bool
    hrv_unreliable = bit_string.read(1).bool
    activity_unreliable = bit_string.read(1).bool
    
    link_quality = bit_string.read(8).uintle
    rssi = bit_string.read(8).intle
    tx_power = bit_string.read(8).intle
    
    estimated_core_temp = bit_string.read(16).uintle * 0.1
    
    # We now create the Summary Message and do not parse from here on as it has nothing that interests us.

    message = SummaryMessage(sequence_number, timestamp, heart_rate, respiration_rate, skin_temperature, posture, activity, peak_acceleration, 
                                battery_volatge, battery_level,  
                                respiration_wave_amplitude, respiration_wave_noise, respiration_wave_confidence,  
                                ecg_wave_amplitude, ecg_wave_noise, ecg_wave_confidence,
                                hrv, system_confidence, 
                                gsr, rog, 
                                accl_vertical_min, accl_vertical_peak, accl_lateral_min, accl_lateral_peak, accl_sagittal_min, accl_sagittal_peak, 
                                device_internal_temp, estimated_core_temp,
                                posture_unreliable, skin_temperature_unreliable, respiration_rate_unreliable, heart_rate_unreliable, estimated_core_temp_unreliable, hrv_unreliable, activity_unreliable,
                                not_fitted_to_garmet, button_pressed, device_worn_detection_level, resting_stage_detection,
                                link_quality, rssi, tx_power)
        
    return message
                                

def signal_packet_payload_parser_factory(sample_parser, signal_code, samplerate):
    def parse_signal_packet(payload):
        sequence_number = payload[0]
        timestamp_bytes = payload[1:9]
        signal_bytes = payload[9:]
        
        message_timestamp = zephyr.util.parse_timestamp(timestamp_bytes)
        samples = sample_parser(signal_bytes)
        
        signal_packet = zephyr.message.SignalPacket(signal_code, message_timestamp, samplerate, samples, sequence_number)
        return signal_packet
    
    return parse_signal_packet

def parse_10_bit_signal_data(signal_bytes):
    samples = zephyr.util.unpack_bit_packed_values(signal_bytes, 10, "uint")
    return samples

def parse_rr_signal_data(signal_bytes):
    samples = zephyr.util.unpack_bit_packed_values(signal_bytes, 16, "intbe")
    return samples


def parse_accelerometer_samples(signal_bytes):
    interleaved_samples = parse_10_bit_samples(signal_bytes)
    
    # 83 correspond to one g in the 14-bit acceleration
    # signal, and this of 1/4 of that
    one_g_value = 20.75
    interleaved_samples = [value / one_g_value for value in interleaved_samples]
    
    # Separating the X Y Z samples into tuples   
    samples = zip(interleaved_samples[0::3],
                        interleaved_samples[1::3],
                        interleaved_samples[2::3])
    return samples


class MessagePayloadParser:
    def __init__(self, callbacks):
        self.callbacks = callbacks
    
    def handle_message(self, message_frame):
        handler = MESSAGE_TYPES.get(message_frame.message_id)
        if handler is not None:
            message = handler(message_frame.payload)
            for callback in self.callbacks:
                callback(message)


MESSAGE_TYPES = {0x2B: parse_summary_packet,
                 0x21: signal_packet_payload_parser_factory(parse_10_bit_signal_data, "breathing", 18.0),
                 0x22: signal_packet_payload_parser_factory(parse_10_bit_signal_data, "ecg", 250.0),
                 0x24: signal_packet_payload_parser_factory(parse_rr_signal_data, "rr", 18.0),
                 0x25: signal_packet_payload_parser_factory(parse_accelerometer_samples, "acceleration", 50.0),
                 0x26: parse_hxm_message}
