## ERPNext FoxyCart integration

An integration app to capture orders processed from FoxyCart into ERPNext

### How to use

 - Install the app
 - Enable datafeed in Foxycart and set the URL to `https://<site>/api/method/erpnext_foxycart_integration.api.push`
 - Set API key used in Foxycart in "Foxycart Settings" 
 - Set other settings accordingly (If you don't set anything, some default values will be used)
 
 Orders will be added as a Draft Sales Order with the correct Customer and Address and Items

#### License

MIT
