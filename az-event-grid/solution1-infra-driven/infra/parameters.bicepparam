using './main.bicep'

param location = 'eastus'
param projectName = 'ipmonitor'
param environment = 'dev'
param vnetAddressPrefix = '10.0.0.0/16'
param subnetAddressPrefix = '10.0.1.0/24'
param functionAppRuntimeVersion = '4.0'
