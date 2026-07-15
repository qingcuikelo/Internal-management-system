import client from './client'

export interface EmployeeAssets {
  workstation: any | null
  devices: any[]
}

export function getEmployeeAssets(employeeId: string) {
  return client.get<any, EmployeeAssets>('/reports/employee-assets', {
    params: { employee_id: employeeId },
  })
}
