def mask_record_by_scope(record_data: dict, scope: str) -> dict:
    data = record_data.copy()
    # 手机号脱敏
    if data.get("phone"):
        data["phone"] = data["phone"][:3] + "****" + data["phone"][-4:]
    # 地址脱敏
    if data.get("address"):
        data["address"] = data["address"].split("，")[0]
    
    # 按权限范围隐藏隐私病历字段
    if scope == "BASIC":
        data["diagnosis"] = "隐私信息已隐藏"
        data["lab_result"] = "隐私信息已隐藏"
        data["medication"] = "隐私信息已隐藏"
    elif scope == "DIAGNOSIS":
        data["lab_result"] = "隐私信息已隐藏"
        data["medication"] = "隐私信息已隐藏"
    elif scope == "LAB":
        data["diagnosis"] = "隐私信息已隐藏"
        data["medication"] = "隐私信息已隐藏"
    elif scope == "MEDICATION":
        data["diagnosis"] = "隐私信息已隐藏"
        data["lab_result"] = "隐私信息已隐藏"
    return data