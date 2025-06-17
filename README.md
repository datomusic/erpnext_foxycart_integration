## ERPNext FoxyCart integration

An integration app to capture orders processed from FoxyCart into ERPNext

### How to use

1.  Install the app on your Frappe/ERPNext site.
2.  In your FoxyCart admin, enable the datafeed and set the URL to: `https://<your-site>/api/method/erpnext_foxycart_integration.api.push`
3.  In ERPNext, go to **Foxycart Settings**.
4.  Enter the **API Key** from your FoxyCart store's integration settings. This is used to decrypt the datafeed.
5.  In the **Payment Gateway Mappings** table, add rows to map the payment gateway names from FoxyCart (e.g., `stripe`, `paypal`, `test_gateway`) to the corresponding **Mode of Payment** and receivable **Payment Account** in ERPNext.
6.  (Optional) Tick the **Submit Sales Order** and/or **Submit Payment Entry** checkboxes if you want these documents to be automatically submitted. By default, they are created as drafts.
7.  Set other default settings like Customer Group and Territory as needed.

By default, when an order is received from FoxyCart, the integration will create a **Draft Sales Order** and a **Draft Payment Entry** linked to it as an advance payment.

#### License

MIT
