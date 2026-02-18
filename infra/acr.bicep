param uniqueId string
param prefix string
param location string = resourceGroup().location
param acrName string = '${prefix}acr${uniqueId}'

resource acr 'Microsoft.ContainerRegistry/registries@2021-06-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic' // Choose between Basic, Standard, and Premium based on your needs
  }
  properties: {
    adminUserEnabled: false
  }
}

output acrName string = acrName
output acrEndpoint string = acr.properties.loginServer
