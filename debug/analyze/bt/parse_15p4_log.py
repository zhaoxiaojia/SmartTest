from .xls_dict import *  # noqa: F401,F403

# 确保'xls_dict.py'中的列表'dict_log_type'存在以下内容
dict_15p4_log_type = {
    0x50: "15p4_general_log",
    0x51: "15p4_performance_log",
    0x52: "15p4_lp_log",
    0x53: "15p4_info_log",
    0x54: "15p4_int_log",
    0x55: "15p4_key_log",
    0x56: "15p4_error_log",
}

# general log的log_type解析列表
dict_15p4_general_log = {}
# key log，info log, int log和errkey log的log_type解析列表
dict_15p4_log = {
    "0x00": "version",
    "0x01": "rf_interrupt",
    "0x02": "uart_interrupt",
    "0x03": "timer",
    "0x04": "channel",
    "0x05": "ack_handle",
    "0x06": "ack_send, fp",
    "0x07": "beacon_send, bsn",
    "0x08": "cmd_id",
    "0x09": "frame_rx_status",
    "0x0a": "frame_tx",
    "0x0b": "frame_rx",
    "0x0c": "frame_pending_tx",
    "0x0d": "frame_tx_status",
    "0x0e": "incoming_superframe_status",
    "0x0f": "outgoing_superframe_status",
    "0x10": "primitives_recv",
    "0x11": "primitives_send",
    "0x12": "beacon_status",
    "0x13": "coex_status",
    "0x14": "beacon_check",
    "0x15": "pib_info",
    "0x16": "comm_status_ind",
    "0x17": "cap_remain",
    "0x18": "time_margin",
    "0x19": "msdu_handle",
    "0x1a": "pending_frame_remove",
    "0x1b": "pending_frame_lookup",
    "0x1c": "15p4_task_msg_id",
    "0x1d": "sys_status",
    "0x1e": "tick",
    "0x1f": "start_time",
    "0x20": "test_num",
    "0x21": "32k_clk",
    "0x22": "dbg",
    "0x23": "test",
    "0x24": "len",
    "0x25": "mic_32",
    "0x26": "sec_in",
    "0x27": "sec_out",
    "0x28": "count",
    "0x29": "timeout",
    "0x2a": "mode",
    "0x2b": "filter mismatch",
    "0x2c": "msg_length",
    "0x2d": "rd_ptr",
    "0x2e": "wr_ptr",
    "0x2f": "sys_time(us)",
    "0x30": "sys_time(slot)",
    "0x31": "warning",
    "0x32": "index",
    "0x33": "assert: malloc failed",
    "0x34": "assert: stack overflow",
    "0x35": "assert",
    "0x36": "exception",
    "0x37": "nmi",
    "0x38": "mcause",
    "0x39": "sp",
    "0x3a": "pc",
    "0x3b": "mstatus",
    "0x3c": "msubm",
    "0x3d": "p_scan_cfm malloc failed",
    "0x3e": "beacon received in other time",
    "0x3f": "uart crc error",
    "0x40": "rf crc error",
    "0x41": "frame len is too short",
    "0x42": "frame counter error",
    "0x43": "creat timer faild",
    "0x44": "invalid timer id",
    "0x45": "out of max timeout",
    "0x46": "invalid cmd id",
    "0x47": "mac_status",
    "0x48": "beacon_send_in_nonbeacon_pan",
    "0x49": "beacon_send_in_beacon_pan",
    "0x4a": "beacon_tx_start",
    "0x4b": "primitives_status",
    "0x4c": "mac_error",
    "0x4d": "primitives_msg_recv",
    "0x4e": "primitives_msg_send",
    "0x4f": "cmd_decode",
    "0x50": "data_decode",
    "0x51": "beacon_decode",
    "0x52": "sec_incoming_aeda",
    "0x53": "sec_outgoing_aeda",
    "0x54": "g_rx_msg_buff malloc failed",
    "0x55": "task_msg_buff malloc failed",
    "0x56": "timeout_msg_buff malloc failed",
    "0x57": "p_sec_frame_buf malloc failed",
    "0x58": "pending_frame_lookup_association_rsp",
    "0x59": "stack high water mark",
    "0x5a": "top of stack",
    "0x5c": "periodic poll req",
    "0x5d": "15.4_wifi_coex_mode",
    # assert log type
    "0x5e": "15.4_assert_id",
    "0x5f": "15.4_assert_data",
    "0x60": "force_switch_to_bt",
    
	"0x80": "network_type",
    "0x81": "msg",
    "0x82": "index",
    "0x83": "15.4_task_remain",
    "0x84": "time_min",
    "0x85": "time_max",
    "0x86": "time_percentage",
    "0x87": "time_total_us",
    "0x88": "arbitrate result",
	"0x89": "broadcast update",
    "0x8a": "forward status",
    "0x8b": "network mesh header",
    "0x8c": "nwk aux sec error",
    "0x8d": "nwk link table age",
    "0x8e": "nwk route id seq age",
	"0x8f": "tx empty",
	"0x90": "timer task remain",
	"0x91": "zigbee forward status",
	"0x92": "zigbee network header",
    # log power log type
    "0xc0": "bt_native_clk",
    "0xc1": "sleep_status",
    "0xc2": "sleep_cycle",
    "0xc3": "sleep_domain",
    "0xc4": "bt_num_links",
    "0xc5": "le_num_links",
    "0xc6": "lp_status",
    "0xc7": "bt_wake_key",
    "0xc8": "le_suspend_start_scan",
    "0xc9": "15p4_check_status",
    "0xca": "bt_check_status",
    "0xcb": "error_reason",
    "0xcc": "wake_src",
    "0xcd": "lp_stack",
    "0xce": "wifi_wake_bt_cnt",
    "0xcf": "lp_sleep_info",

    "0xe0": "wake_start",
    "0xe1": "pmu_wake_done",
    "0xe2": "wake_end",
    "0xe3": "trx_start",
    "0xe4": "trx_end",
    "0xe5": "begin_sleep",
    "0xe5": "sleep_req",
}

# 对特殊log_type的log_data的解析方式
dict_timer = {
    0.0: "SCAN_TIMEOUT_ID",
    1.0: "ASSOCIATION_RSP_TIMEOUT_ID",
    2.0: "RX_EN_TIMEOUT_ID",
    3.0: "ACK_OR_PENDING_DATA_LOST_TIMEOUT_ID",
    4.0: "END_DEVICE_POLL_TIMEOUT_ID",
    5.0: "MAC_15P4_WAKE_HOST_TIMEOUT_ID",
    6.0: "SYS_TICK_ID",
    7.0: "COEX_TIMEOUT_ID",
    8.0: "NWK_THREAD_KEEP_ALIVE_TIMEOUT_ID",
    9.0: "BEACON_TX_TIMEOUT_ID",
    10.0: "OUTGOING_SUPERFRAME_END_TIMEOUT_ID",
    11.0: "BEACON_RX_TIMEOUT_ID",
    12.0: "SYNC_TIMEOUT_ID",
    13.0: "INCOMING_SUPERFRAME_END_TIMEOUT_ID",
    14.0: "GTS_REQ_DEVICE_TIMEOUT_ID",
    15.0: "NWK_THREAD_MLE_ADV_AGE_TIMEOUT_ID",
    16.0: "USB_POLL_PRIMITIVE_ID",
	17.0: "NWK_ZIGBEE_KEEP_ALIVE_TIMEOUT_ID",
    18.0: "NWK_ZIGBEE_NEIGHBOR_TABLE_AGE_TIMEOUT_ID",
}
dict_channel = {
    1 << 11: "HAL_15P4_CH11",
    1 << 12: "HAL_15P4_CH12",
    1 << 13: "HAL_15P4_CH13",
    1 << 14: "HAL_15P4_CH14",
    1 << 15: "HAL_15P4_CH15",
    1 << 16: "HAL_15P4_CH16",
    1 << 17: "HAL_15P4_CH17",
    1 << 18: "HAL_15P4_CH18",
    1 << 19: "HAL_15P4_CH19",
    1 << 20: "HAL_15P4_CH20",
    1 << 21: "HAL_15P4_CH21",
    1 << 22: "HAL_15P4_CH22",
    1 << 23: "HAL_15P4_CH23",
    1 << 24: "HAL_15P4_CH24",
    1 << 25: "HAL_15P4_CH25",
    1 << 26: "HAL_15P4_CH26",
}
dict_cmd_id = {
    1: "MAC_CMD_ASSOCIATION_REQ",
    2: "MAC_CMD_ASSOCIATION_RSP",
    3: "MAC_CMD_DISASSOCIATION_NOTIFICATION",
    4: "MAC_CMD_DATA_REQ",
    5: "MAC_CMD_PANID_CONFLICT_NOTIFICATION",
    6: "MAC_CMD_ORPHAN_NOTIFICATION",
    7: "MAC_CMD_BEACON_REQ",
    8: "MAC_CMD_COORDINATOR_REALIGMENT",
    9: "MAC_CMD_GTS_REQ",
    10: "MAC_CMD_POLL_REQ",
    11: "MAC_CMD_PENDING_DATA_REQ",
    12: "MAC_CMD_FAST_ASSOCIATION_REQ",
    13: "MAC_CMD_COORDINATOR_REALIGMENT_TO_ORPHAN",
}
dict_msg_id = {
    0.0: "MSG_ID_15P4_UART_RX_INT",
    1.0: "MSG_ID_15P4_UART_TX_INT",
    2.0: "MSG_ID_15P4_UART_MSG_SEND",
    3.0: "MSG_ID_15P4_320US_INT",
    4.0: "MSG_ID_15P4_EDSCAN_INT",
    5.0: "MSG_ID_15P4_CSMA_FAIL_INT",
    6.0: "MSG_ID_15P4_TX_INT",
    7.0: "MSG_ID_15P4_RX_INT",
    8.0: "MSG_ID_15P4_TX_FRAME",
    9.0: "MSG_ID_15P4_GTS_TX_FRAME",
    10.0: "MSG_ID_15P4_COEX_RSP",
    11.0: "MSG_ID_15P4_COEX_NOTIFY",
    12.0: "MSG_ID_THREAD_BROADCAST",
    13.0: "MSG_ID_ZIGBEE_BROADCAST",
    14.0: "MSG_ID_15P4_SCAN",
}
dict_incoming_superframe_status = {
    0.0: "SUPERFRAME_RX_INACTIVE",
    1.0: "SUPERFRAME_RX_BEACON_ONGOING",
    2.0: "SUPERFRAME_RX_CAP_ONGOING",
    3.0: "SUPERFRAME_RX_CFP_ONGOING",
}
dict_outgoing_superframe_status = {
    0.0: "SUPERFRAME_TX_INACTIVE",
    1.0: "SUPERFRAME_TX_BEACON_ONGOING",
    2.0: "SUPERFRAME_TX_CAP_ONGOING",
    3.0: "SUPERFRAME_TX_CFP_ONGOING",
}
dict_beacon_status = {
    0.0: "SUPERFRAME_NO_BEACON",
    1.0: "SUPERFRAME_BEACON_NORMAL",
    2.0: "SUPERFRAME_COORDINATOR_REALIGMENT_TX",
    3.0: "SUPERFRAME_WAIT_NEXT_SCH_BEACON",
    4.0: "SUPERFRAME_BEACON_UPDATE",
}
dict_pib_id = {
    0x00: "PHY_PIB_ID_CURRENT_CHANNEL",
    0x02: "PHY_PIB_ID_TX_POWER",
    0x03: "PHY_PIB_ID_CCA_MODE",
    0x04: "PHY_PIB_ID_CURRENT_PAGE",
    0x05: "PHY_PIB_ID_CCA_DURATION",
    0x40: "MAC_PIB_ID_EXTENDED_ADDR",
    0x41: "MAC_PIB_ID_ASSOCIATION_PERMIT",
    0x42: "MAC_PIB_ID_AUTO_REQ",
    0x43: "MAC_PIB_ID_BATTLIFE_EXT",
    0x44: "MAC_PIB_ID_BATTLIFE_EXT_PERIODS",
    0x45: "MAC_PIB_ID_BEACON_PAYLOAD",
    0x46: "MAC_PIB_ID_BEACON_PAYLOAD_LEN",
    0x47: "MAC_PIB_ID_BEACON_ORDER",
    0x48: "MAC_PIB_ID_BEACON_TX_TIME",
    0x4a: "MAC_PIB_ID_COORD_EXTENDED_ADDR",
    0x4b: "MAC_PIB_ID_COORD_SHORT_ADDR",
    0x4e: "MAC_PIB_ID_MAX_CSMA_BACKOFFS",
    0x4f: "MAC_PIB_ID_MIN_BE",
    0x50: "MAC_PIB_ID_PAN_ID",
    0x51: "MAC_PIB_ID_PROMISCUOUS_MODE",
    0x52: "MAC_PIB_ID_RX_ON_WHEN_IDLE",
    0x53: "MAC_PIB_ID_SHORT_ADDR",
    0x54: "MAC_PIB_ID_SUPERFRAME_ORDER",
    0x55: "MAC_PIB_ID_TRANSACTION_PERSISTENCE_TIME",
    0x56: "MAC_PIB_ID_ASSOCIATED_PAN_COORD",
    0x57: "MAC_PIB_ID_MAX_BE",
    0x59: "MAC_PIB_ID_MAX_FRAME_RETRIES",
    0x5a: "MAC_PIB_ID_RSP_WAIT_TIME",
    0x5b: "MAC_PIB_ID_SYNC_SYMBOL_OFFSET",
    0x5c: "MAC_PIB_ID_TIMESTAMP_SUPPORTED",
    0x5d: "MAC_PIB_ID_SEC_ENABLE",
    0x5e: "MAC_PIB_ID_COORD_REALIGN_SEC_LEVEL",
    0x5f: "MAC_PIB_ID_COORD_REALIGN_KEY_ID_MODE",
    0x60: "MAC_PIB_ID_COORD_REALIGN_KEY_SOURCE",
    0x61: "MAC_PIB_ID_COORD_REALIGN_KEY_INDEX",
    0x62: "MAC_PIB_ID_BEACON_SEC_LEVEL",
    0x63: "MAC_PIB_ID_BEACON_KEY_ID_MODE",
    0x64: "MAC_PIB_ID_BEACON_KEY_SOURCE",
    0x65: "MAC_PIB_ID_BEACON_KEY_INDEX",
    0x66: "MAC_PIB_ID_BEACON_AUTO_RSP",
    0x67: "MAC_PIB_ID_BEACON_SYNC_TIMESTAMP",
    0x68: "MAC_PIB_ID_BEACON_SYNC_TIME_OFFSET",
    0x69: "MAC_PIB_ID_TX_BSN",
    0x6a: "MAC_PIB_ID_RX_BSN",
    0x6b: "MAC_PIB_ID_TX_DSN",
    0x6c: "MAC_PIB_ID_RX_DSN",
    0x6d: "MAC_PIB_ID_IMPLICIT_BROADCAST",
    0x6e: "MAC_PIB_ID_KEY_ID_LOOKUP_LIST",
    0x6f: "MAC_PIB_ID_KEY_DECRIPTOR",
    0x70: "MAC_PIB_ID_KEY_USAGE_DESCRIPTOR",
    0x71: "MAC_PIB_ID_KEY_DEVICE_FRAME_COUNTER",
    0x72: "SEC_PIB_ID_DEVICE_LIST",
    0x73: "SEC_PIB_ID_SECLEVEL_LIST",
    0x74: "SEC_PIB_ID_FRAME_COUNTER",
    0x75: "SEC_PIB_ID_AUTO_REQ_SECLEVEL",
    0x76: "SEC_PIB_ID_AUTO_REQ_KEY_ID_MODE",
    0x77: "SEC_PIB_ID_AUTO_REQ_KEY_SOURCE",
    0x78: "SEC_PIB_ID_AUTO_REQ_KEY_INDEX",
    0x79: "SEC_PIB_ID_NEIGHBOR_NODE_CNT  ",
    0x7a: "PHY_PIB_ID_CCA_ED_MODE_THR   ",
    0x7b: "MAC_PIB_ID_DEVICE_TYPE",
    0x7c: "MAC_PIB_ID_LOG_LEVEL_CTRL",
    0x7d: "MAC_PIB_ID_INDIRECT_POLL_RATE",
    0x7e: "MAC_PIB_ID_RSSI",
    0x7f: "MAC_PIB_ID_COEX_STARTEGY",
    0x80: "MAC_PIB_ID_SYS_TIMER",
    0x81: "MAC_PIB_ID_LINK_QUALITY_FLAG",
    0x82: "MAC_PIB_ID_FRAME_TX_IE_PRESENT",
    0x83: "MAC_PIB_ID_FRAME_TX_HEADER_IE_LIST",
    0x84: "MAC_PIB_ID_RAW_DATA_TEST_FLAG",
    0x85: "MAC_PIB_ID_NOTIFY_ALL_BEACON",
    0x86: "MAC_PIB_ID_LIFS_PERIOD",
    0x87: "MAC_PIB_ID_SIFS_PERIOD",
    0x88: "MAC_PIB_ID_GROUP_RX_MODE",
    0x89: "MAC_PIB_ID_CRIT_MSG_DELAY_TOL",
    0x8a: "MAC_PIB_ID_GTS_PERMIT",
    
     #thread offloading pib
    0xA0: "NWK_PIB_ID_MTD_CHILD_ID_TAB", 
    0xA1: "NWK_PIB_ID_FTD_CHILD_ID_TAB",
    0xA2: "NWK_PIB_ID_STATIC_ROUTE_TAB",
    0xA3: "NWK_PIB_ID_STATIC_LINK_TAB",
    0xA4: "NWK_PIB_ID_KEEP_ALIVE_BC_INTERVAL",
    0xA5: "NWK_PIB_ID_PARTITION_ID",
    0xA6: "NWK_PIB_ID_DATA_VERSION",
    0xA7: "NWK_PIB_ID_STABLE_DATA_VERSION",
    0xA8: "NWK_PIB_ID_LEADER_ROUTER_ID",
    0xA9: "NWK_PIB_ID_ROUTE_ID_SEQUENCE",
    0xAA: "NWK_PIB_ID_ROUTE_ID_SEQUENCE_LAST_UPDATE",
    0xAB: "NWK_PIB_ID_ROUTER_ID_SET",
    
    #zigbee offloading pib
	0xB0: "NWK_PIB_ID_ZGB_KEEP_ALIVE_BC_INTERVAL",
	0xB1: "NWK_PIB_ID_ZGB_STATIC_ROUTE_TAB",
	0xB2: "NWK_PIB_ID_ZGB_STATIC_LINK_TAB",
	0xB3: "NWK_PIB_ID_ZGB_SEC_MATERIAL_SET",
	0xB4: "NWK_PIB_ID_ZGB_SEC_FRAME_COUNTER",
	0xB5: "NWK_PIB_ID_ZGB_LINK_STATUS_PERIOD",
}
dict_mid = {
    0.0: "MAC_ID_ASSO_REQ",
    1.0: "MAC_ID_ASSO_IND",
    2.0: "MAC_ID_ASSO_RSP",
    3.0: "MAC_ID_ASSO_CFM",
    4.0: "MAC_ID_BEACON_NOTIFY_IND",
    5.0: "MAC_ID_BEACON_REQ",
    6.0: "MAC_ID_BEACON_CFM",
    7.0: "MAC_ID_BEACON_REQ_IND",
    8.0: "MAC_ID_COMM_STATUS_IND",
    9.0: "MAC_ID_DA_SEND_REQ",
    10.0: "MAC_ID_DA_RECV_IND",
    11.0: "MAC_ID_DA_CFM",
    12.0: "MAC_ID_DISASSO_REQ",
    13.0: "MAC_ID_DISASSO_IND",
    14.0: "MAC_ID_DISASSO_CFM",
    15.0: "MAC_ID_GET_PIB_REQ",
    16.0: "MAC_ID_GET_PIB_CFM",
    17.0: "MAC_ID_ORPHAN_IND",
    18.0: "MAC_ID_ORPHAN_RSP",
    19.0: "MAC_ID_PHY_DETEXT_IND",
    20.0: "MAC_ID_PHY_OP_SWITCH_REQ",
    21.0: "MAC_ID_PHY_OP_SWITCH_IND",
    22.0: "MAC_ID_PHY_OP_SWITCH_CFM",
    23.0: "MAC_ID_POLL_REQ",
    24.0: "MAC_ID_POLL_CFM",
    25.0: "MAC_ID_RESET_REQ",
    26.0: "MAC_ID_RESET_CFM",
    27.0: "MAC_ID_RX_ENABLE_REQ",
    28.0: "MAC_ID_RX_ENABLE_CFM",
    29.0: "MAC_ID_SCAN_REQ",
    30.0: "MAC_ID_SCAN_CFM",
    31.0: "MAC_ID_SET_PIB_REQ",
    32.0: "MAC_ID_SET_PIB_CFM",
    33.0: "MAC_ID_START_PAN_REQ",
    34.0: "MAC_ID_START_PAN_CFM",
    35.0: "MAC_ID_SYNC_REQ",
    36.0: "MAC_ID_SYNC_LOSS_IND",
    37.0: "MAC_ID_DATA_REQ",
    38.0: "MAC_ID_DATA_CFM",
    39.0: "MAC_ID_DATA_IND",
    40.0: "MAC_ID_DATA_PURGE_REQ",
    41.0: "MAC_ID_DATA_PURGE_CFM",
    48.0: "MAC_ID_SCAN_ED",
    49.0: "MAC_ID_SCAN_ACTIVE",
    50.0: "MAC_ID_SCAN_PASSIVE",
    51.0: "MAC_ID_SCAN_ORPHAN",
    52.0: "MAC_ID_GTS_REQ",
    53.0: "MAC_ID_GTS_CFM",
    54.0: "MAC_ID_GTS_IND",
    55.0: "MAC_ID_SLEEP_REQ",
    56.0: "MAC_ID_SCAN_RIT",
    57.0: "MAC_ID_PENDING_COMM_STATUS_IND",
    58.0: "MAC_ID_GET_FW_VERSION_REQ",
	59.0: "MAC_ID_GET_FW_VERSION_CFM",
	60.0: "MAC_ID_IE_IND",
	61.0: "MAC_ID_WIFI_BANDWIDTH_IND",
	62.0: "MAC_ID_POLL_IND",
	63.0: "MAC_ID_RAW_DATA_REQ",
	64.0: "MAC_ID_RAW_DATA_CFM",
	65.0: "MAC_ID_RAW_DATA_IND",
    100.0: "TEST_MAC_ID_CTS_SET_ADDR",
    101.0: "TEST_MAC_ID_CTS_GET_ADDR",
    102.0: "TEST_MAC_ID_CTS_GET_ADDR_CFM",
    103.0: "TEST_MAC_ID_UART_REQ",
    104.0: "TEST_MAC_ID_UART_CTS_REQ",
    105.0: "TEST_MAC_ID_AES_SWTICH_REQ",
    106.0: "TEST_MAC_ID_TIMER_REQ",
    107.0: "TEST_MAC_ID_COEX_SWITCH",
    108.0: "TEST_MAC_ID_TX_RX_REQ",
    109.0: "TEST_MAC_ID_AUTHENTICITY_REQ",
    110.0: "TEST_MAC_ID_CONFIDENTIALITY_REQ",
    111.0: "TEST_MAC_ID_CSMA_REQ",
    112.0: "TEST_MAC_ID_TX_RX_UNSLOT_REQ",
    113.0: "TEST_MAC_ID_DEBUG",
    114.0: "TEST_MAC_ID_CTS_INACTIVE_REQ",
    115.0: "TEST_MAC_ID_ILLEGAL",
}
dict_frame_tx_status = {
    0.0: "FRAME_TX_END",
    1.0: "FRAME_TX_ONGOING",
    2.0: "FRAME_PENDING_TX_ONGOING",
    3.0: "FRAME_BEACON_TX_ONGOING",
    4.0: "FRAME_ACK_TX_ONGOING",
    5.0: "FRAME_GTS_TX_ONGOING",
}
dict_frame_rx_status = {
    0.0: "FRAME_RX_END",
    1.0: "FRAME_RX_ONGING",
    2.0: "FRAME_RX_ACK_ONGOING",
    3.0: "FRAME_RX_PENDING_ONGOING",
}
dict_pending_status = {
    0.0: "NO_PENDING_DATA",
    1.0: "PENDING_FRAME_MATCHED",
    2.0: "PENDING_FRAME_FOR_SHORT",
    3.0: "PENDING_FRAME_FOR_EXT",
    4.0: "PENDING_FRAME_FOR_BROADCAST",
}
dict_coex_status = {
    0.0: "COEX_STATUS_IDLE",
    1.0: "COEX_STATUS_BT",
    2.0: "COEX_STATUS_WIFI",
    3.0: "COEX_STATUS_15P4",
    4.0: "COEX_STATUS_15P4_ONLY",
    5.0: "COEX_STATUS_BT_ONLY",
}
dict_rf_interrupt = {
    1 << 0: "Tx_End",
    1 << 1: "Rx_End",
    1 << 2: "Rx_Sync",
    1 << 3: "Slot",
    1 << 4: "Csma_Fail",
    1 << 5: "ED_Scan",
    1 << 6: "AES_Encrypt End",
    1 << 7: "AES_Decrypt End",
    1 << 8: "Timer",
    1 << 9: "Rx_Sfd_Error",
}
dict_uart_interrupt = {
    1 << 0: "Rx_Threshold",
    1 << 1: "Rx_End",
    1 << 2: "Tx_End",
}
dict_net_status = {
    0: "ZIGBEE",
    1: "THREAD",
}
dict_performance_index = {
    0: "MAC_15P4_INT",
    1: "MAC_15P4_UART_INT",
    2: "MAC_15P4_TIMER_INT",
    3: "MAC_15P4_TASK",
    4: "MAC_15P4_UART_TASK",
    5: "LP_TASK",
    6: "MAC_15P4_COEX_TIME",
}
dict_sys_status = {
    0: "MAC_15P4_SYS_STATUS_IDLE",
    1: "MAC_15P4_SYS_STATUS_EDSCAN",
    2: "MAC_15P4_SYS_STATUS_ACTIVE_SCAN",
    3: "MAC_15P4_SYS_STATUS_PASSIVE_SCAN",
    4: "MAC_15P4_SYS_STATUS_ORPHAN_SCAN",
    5: "MAC_15P4_SYS_STATUS_START_PAN",
    6: "MAC_15P4_SYS_STATUS_COORD_REALIGMENT",
    7: "MAC_15P4_SYS_STATUS_COORD_REALIGMENT_TO_ORPHAN",
    8: "MAC_15P4_SYS_STATUS_ASSOCIATION",
    9: "MAC_15P4_SYS_STATUS_DATA_REQ",
    10: "MAC_15P4_SYS_STATUS_POLL",
    11: "MAC_15P4_SYS_STATUS_PENDING_DATA_REQ",
    12: "MAC_15P4_SYS_STATUS_ASSOCIATION_RSP",
    13: "MAC_15P4_SYS_STATUS_DISASSOCIATION",
    14: "MAC_15P4_SYS_STATUS_SYNCHRONIZATION",
    15: "MAC_15P4_SYS_STATUS_DATA_SEND",
    16: "MAC_15P4_SYS_STATUS_PANID_CONFLICT",
    17: "MAC_15P4_SYS_STATUS_GTS_REQ",
    18: "MAC_15P4_SYS_STATUS_FAST_ASSOCIATION",
    19: "MAC_15P4_SYS_STATUS_RX_NORMAL",
    20: "MAC_15P4_SYS_STATUS_RX_BEACON_ONGOING",
    21: "MAC_15P4_SYS_STATUS_TX_BEACON_ONGOING",
}
dict_frame_type = {
    0: "Beacon",
    1: "Data",
    2: "Ack",
    3: "MAC_Command",
}
dict_mac_status = {
    0x00: "SUCCESS",
    0x01: "BAD_CHANNEL",
    0x02: "IMPROPER_IE_SECURITY",
    0x03: "UNAVAILABLE_DEVICE",
    0x04: "UNAVAILABLE_SECURITY_LEVEL",
    0x05: "UNSUPPORTED_FEATURE_15P4",
    0x06: "UNSUPPORTED_PRF",
    0x07: "UNSUPPORTED_RANGING",
    0x08: "UNSUPPORTED_PSR",
    0x09: "UNSUPPORTED_DATARATE",
    0x0a: "UNSUPPORTED_LEIP",
    0x0b: "ACK_RCVD_NODSN_NOSA",
    0x0c: "ASSOC_PAN_CAPACITY",
    0x0d: "ASSOC_PAN_ACCESS_DENIED",
    0x0e: "ASSOC_HOPPING_SEQUENCE_OFFSET_DUP",
    0x0f: "FAILED",
    0x10: "CONDITIONALLY_PASSED",
    0x11: "NO_SECURITY",
    0x12: "ON_TIME_TOO_SHORT",
    0x13: "NO_ENOUGH_TIME",
    0x14: "RETRANSMISSION_FRAME",
    0x15: "NOT_15P4_TIME_SLOT",
    0x16: "TIME_FOR_15P4",
    0xdb: "COUNTER_ERROR",
    0xdc: "IMPROPER_KEY_TYPE",
    0xdd: "IMPROPER_SECURITY_LEVEL",
    0xde: "UNSUPPORTED_LEGACY",
    0xdf: "UNSUPPORTED_SECURITY",
    0xe0: "BEACON_LOST",
    0xe1: "CHANNEL_ACCESS_FAILURE",
    0xe2: "DENIED",
    0xe4: "SECURITY_ERROR",
    0xe5: "FRAME_TOO_LONG",
    0xe6: "INVALID_GTS",
    0xe7: "INVALID_HANDLE",
    0xe8: "INVALID_PARAMETER",
    0xe9: "NO_ACK",
    0xea: "NO_BEACON",
    0xeb: "NO_DATA",
    0xec: "NO_SHORT_ADDRESS",
    0xee: "PAN_ID_CONFLICT",
    0xef: "REALIGMENT",
    0xf0: "TRANSACTION_EXPIRED",
    0xf1: "TRANSACTION_OVERFLOW",
    0xf3: "UNAVAILABLE_KEY",
    0xf4: "UNSUPPORTED_ATTRIBUTE",
    0xf5: "INVALID_ADDRESS",
    0xf6: "ON_TIME_TOO_LONG",
    0xf7: "PAST_TIME",
    0xf8: "TRACKING_OFF",
    0xf9: "INVALID_INDEX",
    0xfa: "LIMIT_REACHED_15P4",
    0xfb: "READ_ONLY",
    0xfc: "SCAN_IN_PROGRESS",
    0xfd: "SUPERFRAME_OVERLAP",
    0xfe: "OTHER_ERR",
}
dict_mac_error = {
    0.0: "MAC_OK",
    1.0: "MAC_MEM_ALLOCAT_ERR",
    2.0: "MAC_MSG_CRC_ERR",
    3.0: "MAC_MSG_BUF_FULL_ERR",
    4.0: "MAC_MSG_PARAM_ERR",
    5.0: "MAC_MSG_HANDLE_VAL_ERR",
    6.0: "MAC_MSG_LEN_ERR",
    7.0: "MAC_MSG_NOT_ENOUGH_ERR",
    8.0: "MAC_BEACON_TYPE_ERR",
    9.0: "MAC_SCAN_FILTER_ERR",
    10.0: "MAC_FRAME_VERSION_ERR",
    11.0: "MAC_SRC_ADDR_MODE_ERR",
    12.0: "MAC_DST_ADDR_MODE_ERR",
    13.0: "MAC_FRAME_LEN_ERR",
    14.0: "MAC_FRAME_TX_BUF_EMPTY_ERR",
    15.0: "MAC_COORD_SHORT_ADR_NO_MATCH_ERR",
    16.0: "MAC_COORD_EXT_ADR_NO_MATCH_ERR",
    17.0: "MAC_EXT_ADDR_NO_MATCH_ERR",
    18.0: "MAC_SHORT_ADR_NO_MATCH_ERR",
    19.0: "MAC_EXTEND_ADR_MATCH_ERR",
    20.0: "MAC_SHORT_ADR_MATCH_ERR",
    21.0: "MAC_PAN_ID_NO_MATCH_ERR",
    22.0: "MAC_SAME_PANID_ERR",
    23.0: "MAC_BROADCAST_FRAME",
    24.0: "MAC_PAN_COORDINATOR_PANID_CONFLICT_ERR",
    25.0: "MAC_DEVICE_PANID_CONFLICT_ERR",
    26.0: "MAC_PAN_ID_COMPRESS_FIELD_ERR",
    27.0: "MAC_TIME_MAX_ERR",
    28.0: "MAC_TIME_PARAM_ERR",
    29.0: "MAC_TIMEOUT_ERR",
    30.0: "MAC_SEC_MIC_ERR",
    31.0: "MAC_SEC_PARAM_ERR",
    32.0: "MAC_CMD_NOT_MATCH_ERR",
    33.0: "MAC_ACK_SEQ_NOT_MATCH_ERR",
    34.0: "MAC_COEX_TIME_IS_NOT_ENOUGH",
    35.0: "MAC_COEX_WORK_HAS_TO_END",
    36.0: "MAC_MSG_MISALIGN_ERR",
    37.0: "MAC_RX_FRAME_TYPE_ERR",
    38.0: "MAC_CAP_NO_ENOUGH_TIME_ERR",
    39.0: "MAC_UNEXPECT_FRAME_ERR",
    40.0: "MAC_GTS_DEALLOCATION_ERR",
    41.0: "MAC_GTS_ALLOCATED_FULL_ERR",
    42.0: "MAC_GTS_NO_ENOUGH_TIME_ERR",
}
# assert log
dict_15p4_assert_type = {
    0: "ASSERT_ID_UART_BUSY",
}
# low power log
dict_sleep_status = {
    0: "SHUTDOWN",
    1: "DEEP_SLEEP",
    2: "SLEEP",
    3: "LIGHT_SLEEP",
    4: "IDLE",
    5: "ACTIVE",
}
dict_bt_scan_type = {
    0: "BT_SCAN_DISABLE",
    1: "BT_INQUIRY_SCAN",
    2: "BT_PAGE_SCAN",
    3: "BT_INQUIRY_PAGE_SCAN",
}
dict_lp_status = {
	0: "LP_IDLE",
	1: "LP_SHUTDOWN",
	2: "LP_SUSPEND",
	3: "LP_SUSPEND_WAIT",
	4: "LP_WAKE_WAIT_RESUME",
	5: "LP_WAKE_IDLE",
	6: "LP_WAKE_START_LOW",
	7: "LP_WAKE_START_HIGH",
    8: "LP_RESUME",
}
dict_lp_15p4_check_status = {
	(0 << 0): "MAC_15P4_SLEEP_EN",
	(1 << 0): "MAC_NORMAL_TX_BUFFER_IS_NOT_EMPTY",
	(1 << 1): "MAC_FRAME_TX_IS_NOT_END",
	(1 << 2): "MAC_FRAME_RX_IS_NOT_END",
	(1 << 3): "MAC_MSG_TX_BUF_IS_NOT_EMPTY",
	(1 << 4): "MAC_MSG_RX_BUF_IS_NOT_EMPTY",
	(1 << 5): "MAC_MSG_TX_IS_NOT_END",
	(1 << 6): "MAC_MSG_RX_IS_NOT_SLEEP",
    (1 << 15): "MAC_ALWAYS_ACTIVE",
}
dict_lp_bt_check_status = {
	(0 << 0): "BT_SLEEP_EN",
    (1 << 0): "BT_INQUIRY_OR_PAGE_STATE_IS_ACTIVE",
	(1 << 1): "BT_INQUIRY_OR_PAGE_SCAN_STATE_IS_ACTIVE",
	(1 << 2): "BT_SNIFF_STATE_IS_ACTIVE",
	(1 << 3): "LE_CE_IS_ACTIVE",
	(1 << 4): "LE_SCAN_IS_ACTIVE",
	(1 << 5): "BT_CMD_QUEUE_IS_NOT_EMPTY",
	(1 << 6): "BT_HAS_TIMER_EXPIRED",
	(1 << 7): "BT_WIFI_CALI_IS_ONGOING",
    (1 << 8): "BT_HOST_NOT_ALLOWED_SLEEP",
}
# fw log print接口参数与解析接口参数对应关系
# MAC_15P4_LOG_PRINT(build_digit_log(DEFAULT_MASK, log_level, log_type), log_data);


def parse_15p4_log(log_level, log_type, log_data):
    # print("log_level: " + hex(log_level), "", end="\t\t")
    # print("log_type: " + hex(log_type), "", end="\t\t")
    # print("log_data: " + hex(log_data), "", end="\t\t")

    log_level == hex(log_level)

    # log输出前缀
    if int(log_type, 16) >= 0xC0:
        if log_level == 0x50:
            log_header = "[lp general]"
        elif log_level == 0x51:
            log_header = "[lp performance]"
        elif log_level == 0x52:
            log_header = "[low power]"
        elif log_level == 0x53:
            log_header = "[lp info]"
        elif log_level == 0x54:
            log_header = "[lp int]"
        elif log_level == 0x55:
            log_header = "[lp key]"
        elif log_level == 0x56:
            log_header = "[lp err_key]"
    else:
        if log_level == 0x50:
            log_header = "[15p4 general]"
        elif log_level == 0x51:
            log_header = "[15p4 performance]"
        elif log_level == 0x52:
            log_header = "[15p4 lp]"
        elif log_level == 0x53:
            log_header = "[15p4 info]"
        elif log_level == 0x54:
            log_header = "[15p4 int]"
        elif log_level == 0x55:
            log_header = "[15p4 key]"
        elif log_level == 0x56:
            log_header = "[15p4 err_key]"

    # 解析general log
    if log_level == 0x50:
        log_15p4_type = dict_15p4_general_log.get(log_type)
        log_type = int(log_type, 16)
        # 解析dict_15p4_general_log列表中 ### 存在的 ### log type
        if log_15p4_type != None:
            log_dbg = log_header + str(log_15p4_type) + ":"
            print(log_dbg, "", end="")
        # 解析dict_15p4_general_log列表中 ### 不存在的 ### log type
        else:
            log_dbg = log_header + "dbg" + str(log_type) + ":"
            print(log_dbg, "", end="")
        print(hex(log_data), "", end="")

    # 解析key log，info log, int log和error key log，它们的log type解析方式一致，打印优先级不同
    else:
        log_15p4_type = dict_15p4_log.get(log_type)
        log_type = int(log_type, 16)
        # 解析dict_15p4_log列表中 ### 存在的 ### log type
        if log_15p4_type != None:
            log_dbg = log_header + str(log_15p4_type) + ":"
            print(log_dbg, "", end="")
            # 对特殊的log type的log_data进行解析
            if log_type == 0x01:
                for key in dict_rf_interrupt:
                    if log_data & key:
                        log_15p4_data = dict_rf_interrupt.get(log_data, hex(log_data))
                        print(log_15p4_data, "", end="|")
                # print("")
            elif log_type == 0x02:
                for key in dict_uart_interrupt:
                    if log_data & key:
                        log_15p4_data = dict_uart_interrupt.get(log_data, hex(log_data))
                        print(log_15p4_data, "", end="|")
                # print("")
            elif log_type == 0x03:
                log_15p4_data = dict_timer.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x04:
                log_15p4_data = dict_channel.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif (log_type == 0x05) or (log_type == 0x1D):
                log_15p4_data = dict_sys_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x08:
                log_15p4_data = dict_cmd_id.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x0A:
                #   [31-24]   #  [23-16]  #   [15-8]   #
                # frame type  #  seq_num  #   cmd_id   #
                log_15p4_data = dict_frame_type.get(log_data >> 24, hex(log_data))
                print(log_15p4_data, "", end="|")
                print("seq_num: " + hex((log_data >> 16) & 0xFF), "", end="|")
                if log_data >> 24 == 0x03:  # MAC_Command帧才解析cmd id
                    log_15p4_data = dict_cmd_id.get(
                        (log_data >> 8) & 0xFF, hex(log_data)
                    )
                    print(log_15p4_data, "", end="")

            elif log_type == 0x0B:
                #   [31-24]   #  [23-16]  #  #    [15-8]   #
                # frame type  #  seq_num  #  #  rx_status  #
                log_15p4_data = dict_frame_type.get(log_data >> 24, hex(log_data))
                print(log_15p4_data, "", end="|")
                print("seq_num: " + hex((log_data >> 16) & 0xFF), "", end="|")
                log_15p4_data = dict_mac_error.get((log_data >> 8) & 0xFF, hex(log_data))
                print("rx_status: " + log_15p4_data, "", end="|")

            elif log_type == 0x0C:
                #   [31-24]   #  [23-16]  #   [15-8]   #    [7-0]    #
                # frame type  #  seq_num  #   cmd_id   # msdu_handle #
                log_15p4_data = dict_frame_type.get(log_data >> 24, hex(log_data))
                print(log_15p4_data, "", end="|")
                print("seq_num: " + hex((log_data >> 16) & 0xFF), "", end="|")
                if log_data >> 24 == 0x03:  # MAC_Command帧才解析cmd id
                    log_15p4_data = dict_cmd_id.get(
                        (log_data >> 8) & 0xFF, hex(log_data)
                    )
                    print(log_15p4_data, "", end="|")
                print("msdu_handle: " + hex(log_data & 0xFF), "", end="")

            elif log_type == 0x0E:
                log_15p4_data = dict_incoming_superframe_status.get(
                    log_data, hex(log_data)
                )
                print(log_15p4_data, "", end="")
            elif log_type == 0x0F:
                log_15p4_data = dict_outgoing_superframe_status.get(
                    log_data, hex(log_data)
                )
                print(log_15p4_data, "", end="")

            elif (log_type == 0x10) or (log_type == 0x11):
                log_15p4_data = dict_mid.get(log_data)
                print(log_15p4_data, "", end="")

            elif log_type == 0x12:
                log_15p4_data = dict_beacon_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x13:
                log_15p4_data = dict_coex_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x14:
                log_15p4_data = dict_mac_error.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x15:
                #   [31-24]   #  [23-16]  #   [15-0]   #
                #   pib_id    #  sub_id1  #   sub_id2  #
                log_15p4_data = dict_pib_id.get(log_data >> 24, hex(log_data))
                print(log_15p4_data, "", end="|")
                print("sub_id1: " + hex((log_data >> 16) & 0xFF), "", end="|")
                print("sub_id2: " + hex(log_data & 0xFFFF), "", end="")

            elif log_type == 0x16:
                log_15p4_data = dict_mac_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x1A:
                #  [23-16]  #   [15-8]   #   [7-0]  #
                #   index   # frame_ctrl #  seq_num #
                print("index: " + hex((log_data >> 16)), "", end="|")
                log_15p4_data = dict_frame_type.get(
                    (log_data >> 8) & 0x3, hex((log_data >> 8) & 0x3)
                )
                print(
                    "frame_ctrl: "
                    + hex((log_data >> 8) & 0xFF)
                    # + "(ft:"
                    # + log_15p4_data
                    # + " se:"
                    # + hex((log_data >> 8) & 0x4)
                    # + " fp:"
                    # + hex((log_data >> 8) & 0x8)
                    # + " ar:"
                    # + hex((log_data >> 8) & 0x10)
                    # + " pic:"
                    # + hex((log_data >> 8) & 0x20)
                    # + ")"
                    ,
                    "",
                    end="|",
                )
                print("seq_num: " + hex(log_data & 0xFF), "", end="")
            elif log_type == 0x1C:
                log_15p4_data = dict_msg_id.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            elif log_type == 0x1E:
                sys_time_hou = log_data // (1000000 * 60) // 60
                sys_time_min = log_data // (1000000 * 60) % 60
                sys_time_sec = log_data // (1000000) % 60
                sys_time_ms = (
                    log_data
                    - ((sys_time_hou * 60 + sys_time_min) * 60 + sys_time_sec)
                    * (1000000)
                ) // 1000
                log_15p4_data = (
                    str(int(sys_time_hou))
                    + ":"
                    + str(int(sys_time_min))
                    + ":"
                    + str(int(sys_time_sec))
                    + "."
                    + str(int(sys_time_ms))
                )

                print(log_15p4_data, "", end="")

            elif log_type == 0x0D:
                log_15p4_data = dict_frame_tx_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x09:
                log_15p4_data = dict_frame_rx_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            # elif log_type == 0x25:
            #     log_15p4_data = dict_pending_status.get(log_data)
            #     print(log_15p4_data, "", end="")

            elif (log_type >= 0x47) and (log_type <= 0x4B):
                log_15p4_data = dict_mac_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif ((log_type >= 0x4C) and (log_type <= 0x53)) or (log_type == 0x2B):
                log_15p4_data = dict_mac_error.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x44:
                log_15p4_data = dict_timer.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x5c:
                if log_data == 1:
                    print("start", "", end="")
                else:
                    print("stop", "", end="")
            elif log_type == 0x5d:
                if log_data == 0x11:
                    print("in_the_same_frequency || wifi_calibration", "", end="")
                elif log_data == 0x10:
                    print("in_the_same_frequency || wifi_not_calibration", "", end="")
                elif log_data == 0x01:
                    print("in_the_diff_frequency || wifi_calibration", "", end="")
                else:
                    print("in_the_diff_frequency || wifi_not_calibration", "", end="")
            elif log_type == 0x5e:
                log_15p4_data = dict_15p4_assert_type.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x5f:
                print(hex(log_data), "", end="")
            elif log_type == 0x60:
                print(hex(log_data), "", end="")
            elif log_type == 0x80:
                log_15p4_data = dict_net_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x82:
                print((log_data), "", end="")
            elif log_type == 0x83:
                log_15p4_data = dict_performance_index.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0x85:
                print((log_data), "", end="")
            elif log_type == 0x86:
                print((log_data), "", end="")
            elif log_type == 0x87:
                print((log_data), "", end="")
            elif log_type == 0x88:
                print((hex(log_data)), "", end="")
            ### low power
            elif log_type == 0xC0:
                log_15p4_data = str(hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0xC1:
                log_15p4_data = dict_sleep_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0xC2:
                log_15p4_data = str(int(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0xC4:
                log_15p4_data = dict_bt_scan_type.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0xC6:
                log_15p4_data = dict_lp_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0xC9:
                log_15p4_data = dict_lp_15p4_check_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")
            elif log_type == 0xCA:
                log_15p4_data = dict_lp_bt_check_status.get(log_data, hex(log_data))
                print(log_15p4_data, "", end="")

            # log data不需要解析则直接打印
            else:
                print(hex(log_data), "", end="")

        # 解析dict_15p4_log列表中 ### 不存在的 ### log type
        else:
            log_dbg = log_header + "dbg" + str(log_type)
            print(log_dbg, "", end=":")
            print(hex(log_data), "", end="")
