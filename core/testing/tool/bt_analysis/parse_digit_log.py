#!/usr/bin/python
# -*- coding: UTF-8 -*-

# frame format
# # # # # # # # # # # # # # # # # # # #
#   [0]   #    [1-7]    #   [8-15]    #
# # # # # # # # # # # # # # # # # # # #
# status  #  log type   #  log body   #
# # # # # # # # # # # # # # # # # # # #

import hashlib
import os
import sys

import xlrd
import time
import datetime
from .xls_dict import *
from .parse_15p4_log import *
g_timestamp = ''
fd = None
locals_dict = locals()
def read_byte_to_str_org():
    read_byte = fd.read(3)
    # print('jh hello www')
    # print(read_byte)
    if (str(read_byte) != ""):
        # print('read byte {}'.format(read_byte))
        read_byte = read_byte[0:2]
        # print('read byte {}'.format(read_byte))

    else:
        print("\nlog parse end")

    return read_byte


def read_byte_to_str():
    global g_timestamp
    read_byte = fd.read(3)
    read_byte_hex = ''
    if str(read_byte) != "":
        read_byte_hex = read_byte[0:2]
    else:
        print("\nlog parse end")
    # print('read byte {}'.format(read_byte))

    if str(read_byte) == '202':
        # print("time stamp get. skip some 27 chars ")
        # fd.seek(-3, 1)
        fd.seek((fd.tell() - 3), os.SEEK_SET)  # 当预定义log解析错误时，丢弃并打印
        # get time stamp
        read_timestamp = fd.read(27)
        g_timestamp = read_timestamp[0:]
        # print("time : {}".format(g_timestamp))
        read_byte_hex = read_byte_to_str_org()
        # print(g_timestamp)

    return read_byte_hex


def read_byte_to_int():
    read_byte = read_byte_to_str()
    if (str(read_byte) != ""):
        read_byte = int(read_byte, 16)

    return read_byte


def parse_log_head(msg_head):
    # bit1-bit7
    log_type = (msg_head) & (0x7f)

    if ((log_type & 0xf0) == 0):
        log_type = hex(log_type)
        log_type = log_type[0:2] + "0" + log_type[2:3]
    else:
        log_type = hex(log_type)

    log_type = log_type.lower()

    # print("log_type:", log_type, " ",  end='')
    # if( log_type in dict_log_type ):
    #    print (dict_log_type.get(log_type) , " ",  end='')
    # else:
    #    print ( "log_type_error" )

    if ((dict_log_type.get(log_type) == "pure_data") or (dict_log_type.get(log_type) == "verify_type")):
        pass

    else:
        print(" ")
        print(g_timestamp, end='')

        # bit0：0 tx, 1 rx
        if ((dict_log_type.get(log_type) == "acl_data") or (dict_log_type.get(log_type) == "sco_data")):
            tx_rx_mask = (msg_head >> 7) & (0x1)
            if (tx_rx_mask == 0):
                print("tx_data:", end='')
            elif (tx_rx_mask == 1):
                print("rx_data:", end='')

        if ((dict_log_type.get(log_type) == "seqn_msg")):
            tx_rx_mask = (msg_head >> 7) & (0x1)
            if (tx_rx_mask == 0):
                print("tx_seqn:", end='')
            elif (tx_rx_mask == 1):
                print("rx_seqn:", end='')

        if ((dict_log_type.get(log_type) == "LMP_PDU") or (dict_log_type.get(log_type) == "LE_LL_Control_PDU") or \
                (dict_log_type.get(log_type) == "LE_adv_pdu") or (dict_log_type.get(log_type) == "le_tx_rx_len")):
            tx_rx_mask = (msg_head >> 7) & (0x1)
            if (tx_rx_mask == 0):
                print("tx:", end='')
            elif (tx_rx_mask == 1):
                print("rx:", end='')

        if (dict_log_type.get(log_type) == "ack_nak"):
            tx_rx_mask = (msg_head >> 7) & (0x1)
            if (tx_rx_mask == 0):
                print("tx_ack:", end='')
            elif (tx_rx_mask == 1):
                print("rx_ack:", end='')

        if ((dict_log_type.get(log_type) == "link_id")):
            tx_rx_mask = (msg_head >> 7) & (0x1)
            # print ("link_id:", end='')
            if (tx_rx_mask == 0):
                print("tx_link:", end='')
            elif (tx_rx_mask == 1):
                print("rx_link:", end='')

        if ((dict_log_type.get(log_type) == "role_log")):
            print("p_role:", end='')

        if (dict_log_type.get(log_type) == "Packet_type"):
            tx_rx_mask = (msg_head >> 7) & (0x1)
            if (tx_rx_mask == 0):
                print("tx_pkt:", end='')
            elif (tx_rx_mask == 1):
                print("rx_pkt:", end='')

        # bit0：0 enc_cnt, 1 dec_cnt
        elif (dict_log_type.get(log_type) == ("enc_dec_counter")):
            enc_dec_mask = (msg_head >> 7) & (0x1)
            if (enc_dec_mask == 0):
                print("enc:", end='')
            elif (enc_dec_mask == 1):
                print("dec:", end='')

        # bit0：0 switch_to_class, 1 switch_to_class
        elif (dict_log_type.get(log_type) == ("classic_le_switch")):
            cla_le_mask = (msg_head >> 7) & (0x1)
            if (cla_le_mask == 0):
                print("sw_to_cla:", end='')
            elif (cla_le_mask == 1):
                print("sw_to_le:", end='')

    return log_type


def start_parse_fw_log(__filename, is_normal_mode, addtimestamp, logcat_name):
    global fd
    global g_timestamp
    g_timestamp = ''
    # In the integrated tool we always pass the concrete filename and
    # capture output at a higher layer, so the legacy special-casing of
    # ``com_tool/fw_log.txt`` and internal stdout redirection are no
    # longer required.
    origin_log_path = __filename
    print("start parse bt firmware log ")

    fd = open(origin_log_path)

    var_verify1 = 0
    var_verify2 = 0
    last_byte_verify = 0

    high_8bit_opcode = ''
    low_8bit_opcode = ''
    hci_cmd_cnt = 0
    pure_data_15p4 = 0
    log_15p4_level = None
    log_15p4_type = None
    done = 0
    while not done:
        high_byte = read_byte_to_int()
        # print(g_timestamp, end='')
        # break
        if str(high_byte) != "":
            var_verify1 = int(high_byte)

            if last_byte_verify == var_verify1 == 0xFF:
                last_byte_verify = var_verify1
                # print("verify11")
                pass
            else:
                last_byte_verify = var_verify1
                log_type = parse_log_head(high_byte)

                log_body = read_byte_to_str()
                # print (" byte:", hex(high_byte), " ", log_body, " ", end='')

                if str(log_body) != "":
                    log_body = log_body.lower()
                    var_verify2 = int(log_body, 16)

                    if last_byte_verify == var_verify2 == 0xFF:
                        last_byte_verify = var_verify2
                        # print("verify22")
                        pass
                    else:
                        last_byte_verify = var_verify2

                        # parse log body
                        if dict_log_type.get(log_type) == "pure_data":
                            if log_15p4_level != None:
                                pure_data_15p4 <<= 8
                                pure_data_15p4 += int(log_body, 16)
                                # old 15.4 log print type
                                # print(log_body, " ", end="")
                            else:
                                print(log_body, " ", end="")
                                # print(pure_data_15p4, " ", end="")
                                # print (int(log_body, 16), " ",  end='')
                                # print ((str(int(log_body, 16))).rjust(3), " ",  end='')
                                # print ((str(int(log_body, 16))).rjust(3, '0'), " ",  end='')
                                # pass
                        # hci opcode 16bit
                        else:
                            if log_15p4_level != None:
                                # new 15.4 log print type
                                parse_15p4_log(
                                    log_15p4_level, log_15p4_type, pure_data_15p4
                                )
                                log_15p4_level = None
                                log_15p4_type = None
                                pure_data_15p4 = 0
                                if (
                                    (dict_log_type.get(log_type) != "15p4_error_log")
                                    and (dict_log_type.get(log_type) != "15p4_key_log")
                                    and (dict_log_type.get(log_type) != "15p4_int_log")
                                    and (dict_log_type.get(log_type) != "15p4_info_log")
                                    and (dict_log_type.get(log_type) != "15p4_lp_log")
                                    and (dict_log_type.get(log_type) != "15p4_performance_log")
                                    and (dict_log_type.get(log_type) != "15p4_general_log")
                                ):
                                    print("\n")

                            if dict_log_type.get(log_type) == "HCI_Command":
                                # hci_cmd_opcode = parse_HCI_Command(log_body)
                                if hci_cmd_cnt == 0:
                                    high_8bit_opcode = log_body
                                    hci_cmd_cnt += 1
                                    continue
                                elif hci_cmd_cnt == 1:
                                    low_8bit_opcode = log_body

                                hci_cmd_cnt += 1

                                if hci_cmd_cnt == 2:
                                    hci_cmd_opcode = (
                                        "0x" + high_8bit_opcode + low_8bit_opcode
                                    )
                                    hci_cmd_opcode = hci_cmd_opcode.lower()
                                    # print(g_timestamp, end='')
                                    print("cmd_op:", hci_cmd_opcode)
                                    # print ("hci_cmd_opcode:", hci_cmd_opcode, " ",  end='')
                                    log_body = (
                                        locals_dict["dict_" + dict_log_type.get(log_type)]
                                    ).get(hci_cmd_opcode)
                                    # print(g_timestamp, end='')
                                    print((str(log_body)).lower(), " ", end="")
                                    hci_cmd_cnt = 0

                            else:
                                log_body = "0x" + log_body
                                # print ("log_body:", log_body, " ", end='\n')
                                # temp dbg message

                                # if dict_log_type.get(log_type) is "debug_log_msg":
                                #     log_15p4_type = (
                                #         locals()["dict_" + dict_log_type.get(log_type)]
                                #     ).get(log_body)
                                #     if log_15p4_type != None:
                                #         log_dbg = str(log_15p4_type) #+ str(int(log_body[2:4], 16))
                                #         print('{0:<16}'.format(log_dbg), " ", end="\t")
                                #     else:
                                #         log_dbg = "dbg" + str(int(log_body[2:4], 16))
                                #         print('{0:<16}'.format(log_dbg), " ", end="\t")
                                if (
                                    (dict_log_type.get(log_type) == "15p4_error_log")
                                    or (dict_log_type.get(log_type) == "15p4_key_log")
                                    or (dict_log_type.get(log_type) == "15p4_int_log")
                                    or (dict_log_type.get(log_type) == "15p4_info_log")
                                    or (dict_log_type.get(log_type) == "15p4_lp_log")
                                    or (dict_log_type.get(log_type) == "15p4_performance_log")
                                    or (dict_log_type.get(log_type) == "15p4_general_log")
                                ):
                                    log_15p4_level = int(log_type, 16)
                                    log_15p4_type = log_body

                                elif dict_log_type.get(log_type) == "debug_log_msg":
                                    log_dbg = "dbg" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")

                                elif dict_log_type.get(log_type) == "pc_debug_log_msg":
                                    log_dbg = "dbg_pc" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")

                                elif dict_log_type.get(log_type) == "xyz_debug_log_msg":
                                    log_dbg = "dbg_sjr" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")

                                elif dict_log_type.get(log_type) == "sjr_debug_log_msg":
                                    log_dbg = "dbg_xyz" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "jkm_debug_log_msg":
                                    log_dbg = "dbg_jikai" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="") 
                                elif dict_log_type.get(log_type) == "bei_debug_log_msg":
                                    log_dbg = "dbg_bei" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "init_debug_log_msg":
                                    log_dbg = "dbg_init" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "isoal_debug_log_msg":
                                    log_dbg = "[LE]MSG_ISOAL" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")

                                elif dict_log_type.get(log_type) == "big_debug_log_msg":
                                    log_dbg = "[LE]MSG_BIG" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")

                                elif dict_log_type.get(log_type) == "cig_debug_log_msg":
                                    #log_dbg = "[LE]MSG_CIG" + str(int(log_body[2:4], 16))
                                    log_dbg = "[LE]MSG_CIG:" + log_body;
                                    print(log_dbg, " ", end="")

                                elif dict_log_type.get(log_type) == "le_audio_debug_log_msg":
                                    log_dbg = "[LE]MSG_LE_AUDIO" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "pawr_debug_log_msg":
                                    log_dbg = "[LE]MSG_PAWR" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "le_conn_debug_log_msg":
                                    log_dbg = "[LE]MSG_LE_CONN" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "le_adv_debug_log_msg":
                                    log_dbg = "[LE]MSG_LE_ADV" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "le_scan_debug_log_msg":
                                    log_dbg = "[LE]MSG_LE_SCAN" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "le_ll_debug_log_msg":
                                    log_dbg = "[LE]MSG_LE_LL" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "le_comm_debug_log_msg":
                                    log_dbg = "[LE]MSG_LE_COMM" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "event_list_debug_log_msg":
                                    log_dbg = "[LE]MSG_EVENT_LIST" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")
                                elif dict_log_type.get(log_type) == "host_if_debug_log_msg":
                                    log_dbg = "[LE]MSG_HOST_IF" + str(int(log_body[2:4], 16))
                                    print(log_dbg, " ", end="")

                                # q_full
                                elif dict_log_type.get(log_type) == ("queue_full"):
                                    print("q_full", " ", end="")

                                # le_tx_rx_len
                                elif dict_log_type.get(log_type) == ("le_tx_rx_len"):
                                    print("le_len", log_body, " ", end="")

                                # version
                                elif dict_log_type.get(log_type) == ("version_msg"):
                                    print("version:", log_body, " ", end="")

                                # bt_clock_msg
                                elif dict_log_type.get(log_type) == ("bt_clock_msg"):
                                    print("bt_clock::", log_body, " ", end="")

                                # elif(dict_log_type.get(log_type) is ( "seqn_msg" ) ):
                                #    print ("seqn:",  log_body, " ", end='')

                                elif (
                                    (dict_log_type.get(log_type) == ("link_id"))
                                    or (dict_log_type.get(log_type) == ("acl_data"))
                                    or (dict_log_type.get(log_type) == ("sco_data"))
                                    or (dict_log_type.get(log_type) == ("enc_dec_counter"))
                                    or (
                                        dict_log_type.get(log_type) == ("classic_le_switch")
                                    )
                                ):
                                    print(log_body, " ", end="")

                                # elif( (dict_log_type.get(log_type) is ("trig_msg")) ):
                                #    pass

                                elif dict_log_type.get(log_type) == "verify_type":
                                    pass

                                else:
                                    if log_type in dict_log_type:
                                        if log_body in (
                                            locals_dict["dict_" + dict_log_type.get(log_type)]
                                        ):
                                            log_body = (
                                                locals_dict[
                                                    "dict_" + dict_log_type.get(log_type)
                                                ]
                                            ).get(log_body)
                                            print((str(log_body)).lower(), " ", end="")
                                        else:
                                            fd.seek(
                                                (fd.tell() - 3), os.SEEK_SET
                                            )  # 当预定义log解析错误时，丢弃并打印
                                            print(
                                                "error_log_body,",
                                                "log_type:",
                                                dict_log_type.get(log_type),
                                            )
                                            pass

                                    else:
                                        print(
                                            "parse_log_error,",
                                            "log_type:",
                                            log_type,
                                            "log_body:",
                                            log_body,
                                        )
                else:
                    done = 1
        else:
            done = 1

    fd.close()

    print("parse bt firmware log finished...")
    

