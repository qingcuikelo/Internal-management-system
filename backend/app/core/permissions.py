DEPARTMENT_VIEW = "department:view"
DEPARTMENT_CREATE = "department:create"
DEPARTMENT_UPDATE = "department:update"
DEPARTMENT_DELETE = "department:delete"
EMPLOYEE_VIEW = "employee:view"
EMPLOYEE_CREATE = "employee:create"
EMPLOYEE_UPDATE = "employee:update"
EMPLOYEE_DELETE = "employee:delete"
EMPLOYEE_RESIGN = "employee:resign"
EMPLOYEE_IMPORT = "employee:import"
EMPLOYEE_EXPORT = "employee:export"
WORKSTATION_VIEW = "workstation:view"
WORKSTATION_MANAGE = "workstation:manage"
DEVICE_VIEW = "device:view"
DEVICE_MANAGE = "device:manage"
REPORT_VIEW = "report:view"
SYSTEM_USER = "system:user"
SYSTEM_ROLE = "system:role"
SYSTEM_LOG = "system:log"
SYSTEM_DICT = "system:dict"

ALL_PERMISSIONS: list[dict] = [
    {"code": DEPARTMENT_VIEW, "name": "查看部门", "module": "department"},
    {"code": DEPARTMENT_CREATE, "name": "新增部门", "module": "department"},
    {"code": DEPARTMENT_UPDATE, "name": "编辑部门", "module": "department"},
    {"code": DEPARTMENT_DELETE, "name": "删除部门", "module": "department"},
    {"code": EMPLOYEE_VIEW, "name": "查看员工", "module": "employee"},
    {"code": EMPLOYEE_CREATE, "name": "新增员工", "module": "employee"},
    {"code": EMPLOYEE_UPDATE, "name": "编辑员工", "module": "employee"},
    {"code": EMPLOYEE_DELETE, "name": "删除员工", "module": "employee"},
    {"code": EMPLOYEE_RESIGN, "name": "离职处理", "module": "employee"},
    {"code": EMPLOYEE_IMPORT, "name": "导入员工", "module": "employee"},
    {"code": EMPLOYEE_EXPORT, "name": "导出员工", "module": "employee"},
    {"code": WORKSTATION_VIEW, "name": "查看工位", "module": "workstation"},
    {"code": WORKSTATION_MANAGE, "name": "工位管理", "module": "workstation"},
    {"code": DEVICE_VIEW, "name": "查看设备", "module": "device"},
    {"code": DEVICE_MANAGE, "name": "设备管理", "module": "device"},
    {"code": REPORT_VIEW, "name": "查看报表", "module": "report"},
    {"code": SYSTEM_USER, "name": "账号管理", "module": "system"},
    {"code": SYSTEM_ROLE, "name": "角色权限", "module": "system"},
    {"code": SYSTEM_LOG, "name": "操作日志", "module": "system"},
    {"code": SYSTEM_DICT, "name": "数据字典", "module": "system"},
]
