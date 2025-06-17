import frappe
import json
import hashlib
import hmac

from .foxyutils import decrypt_data
from werkzeug.wrappers import Response

from frappe.utils import cint, nowdate

@frappe.whitelist(allow_guest=True)
def push():
	

	# Get API key and validate the signature of the request
	api_key = frappe.get_single("Foxycart Settings").get_password("api_key")
	signature = hmac.new(api_key.encode("utf-8"), frappe.request.data, hashlib.sha256).hexdigest()

	# If the signature matches, we can assume it's a payload from Foxy.io
	if signature == frappe.request.headers.get("Foxy-Webhook-Signature") and frappe.request.method == "POST":
		response = Response()

		# Try creating a sales order and connected models with the payload
		try:
			fd = json.loads(frappe.request.data)
			process_new_order(fd)
			return Response("done")
		except Exception as e:
			# Log to Frappe error log
			frappe.log_error(e)
			return Response(f"Error: {e}")

		return response

	# Otherwise, treat the incoming request as invalid
	else:
		print("Invalid request")
		response = Response()
		response.status = 500
		return response
	

def process_new_order(foxycart_data):
	foxycart_settings = frappe.get_single("Foxycart Settings")
	customer = find_customer(foxycart_data.get("customer_email"))

	# Hack to prevent permission issues
	if frappe.session.user == "Guest":
		frappe.set_user("Administrator")

	address = None
	if not customer:
		customer = make_customer(foxycart_data, foxycart_settings)
		address = make_address(customer, foxycart_data)
	else:
		address = find_address(customer, foxycart_data)
		if not address:
			address = make_address(customer, foxycart_data)

	sales_order = make_sales_order(customer, address, foxycart_data, foxycart_settings)
	make_payment_entry(customer, sales_order, foxycart_data, foxycart_settings)
	frappe.db.commit()

def find_customer(customer_email):
	customer = frappe.get_all("Customer", filters={"customer_email": customer_email})
	if customer:
		return customer[0].name
	else:
		return None


def make_customer(foxycart_data, foxycart_settings):
	customer = frappe.get_doc({
		"doctype": "Customer",
		"customer_name": (foxycart_data.get("customer_first_name") + " " + foxycart_data.get("customer_last_name")).title(),
		"customer_email": foxycart_data.get("customer_email"),
		"customer_type": foxycart_settings.customer_type or "Individual",
		"customer_group": foxycart_settings.customer_group or "Individual",
		"territory": foxycart_data.get("customer_country") or foxycart_data.get("country") or foxycart_settings.territory or "All Territories"
	})
	customer.flags.ignore_permissions=True
	customer.insert()
	# customer.save()
	frappe.db.commit()
	return customer.name


def make_sales_order(customer, address, foxycart_data, foxycart_settings):
	sales_order = frappe.new_doc("Sales Order")
	sales_order.update({
		"customer": customer,
		"order_type": "Shopping Cart",
		"po_no": foxycart_data.get("id")

	})
	sales_items = []
	
	foxy_items = foxycart_data.get("_embedded").get("fx:items")

	if type(foxy_items) == dict:
		foxy_items = [foxy_items]

	for item in foxy_items:
		product_name = item.get("name")

		if not frappe.db.exists("Item", {"item_name" : product_name}):
			print("Product: {0} not found".format(product_name))

		else:
			item_code = frappe.db.get_value("Item", {"item_name" : product_name}, "name")
			sales_items.append({
				"item_code": item_code,
				"delivery_date": nowdate(),
				"qty": item.get("quantity"),
				"rate": item.get("price")
			})

	sales_order.set("items", sales_items)
	
	# taxes = []
	# if cint(foxycart_data.get("shipping_total")) or foxycart_data.get("shipto_shipping_service_description"):
	# 	taxes.append({
	# 		"charge_type": "Actual",
	# 		"account_head": foxycart_settings.shipping_account_head,
	# 		"description": foxycart_data.get("shipto_shipping_service_description", "Shipping Charges"),
	# 		"tax_amount": cint(foxycart_data.get("shipping_total"))
	# 	})

	# if cint(foxycart_data.get("tax_total")) > 0:
	# 	taxes.append({
	# 		"charge_type": "Actual",
	# 		"account_head": foxycart_settings.tax_account_head,
	# 		"description": "Tax",
	# 		"tax_amount": cint(foxycart_data.get("tax_total"))
	# 	})
	sales_order.set("taxes", [])

	sales_order.customer_address = address
	sales_order.shipping_address_name = address
	sales_order.save(ignore_permissions = True)
	
	if foxycart_settings.submit_sales_order:
		sales_order.submit()

	return sales_order


def make_payment_entry(customer, sales_order, foxycart_data, foxycart_settings):
	# Get payment gateway from foxycart data
	try:
		# Foxycart can have multiple transactions, we'll use the first one
		transaction = foxycart_data.get("_embedded").get("fx:transactions")[0]
		gateway_name = transaction.get("type")
	except (IndexError, AttributeError, TypeError):
		frappe.log_error("Could not find payment gateway in FoxyCart data", "FoxyCart Integration Error")
		return

	# Find matching payment gateway mapping in settings
	payment_mapping = None
	for mapping in foxycart_settings.payment_gateway_mappings:
		if mapping.foxycart_gateway_name == gateway_name:
			payment_mapping = mapping
			break
	
	if not payment_mapping:
		frappe.log_error("No payment mapping found for gateway: {0}".format(gateway_name), "FoxyCart Integration Error")
		return

	# Create Payment Entry
	payment_entry = frappe.new_doc("Payment Entry")
	payment_entry.payment_type = "Receive"
	payment_entry.mode_of_payment = payment_mapping.mode_of_payment
	payment_entry.party_type = "Customer"
	payment_entry.party = customer
	payment_entry.paid_amount = foxycart_data.get("total")
	payment_entry.received_amount = foxycart_data.get("total")
	payment_entry.paid_to = payment_mapping.payment_account
	payment_entry.reference_no = foxycart_data.get("id")
	payment_entry.reference_date = foxycart_data.get("transaction_date")

	payment_entry.append("references", {
		"reference_doctype": "Sales Order",
		"reference_name": sales_order.name,
		"allocated_amount": foxycart_data.get("total")
	})

	payment_entry.flags.ignore_permissions = True
	payment_entry.save()

	if foxycart_settings.submit_payment_entry:
		payment_entry.submit()

	return payment_entry

def find_address(customer, foxycart_data):
	shipping_data = foxycart_data.get('_embedded').get("fx:shipments")[0]

	address = frappe.get_all("Address", filters={
		"address_title": '%s %s' % (shipping_data.get("first_name"), shipping_data.get("last_name")),
		"address_line1": shipping_data.get("address1"),
		"address_line2": shipping_data.get("address2"),
		"address_type": "Shipping",
		"city": shipping_data.get("city"),
		"state": shipping_data.get("region"),
		"pincode": shipping_data.get("postal_code")
	})
	if address:
		return address[0].name

def make_address(customer, foxycart_data):
	print(foxycart_data)
	address = frappe.new_doc("Address")

	shipping_data = foxycart_data.get('_embedded').get("fx:shipments")[0]
	customer_data = foxycart_data.get('_embedded').get("fx:customer")
	
	if shipping_data:
		country_code = shipping_data.get("country")

		country = frappe.get_all("Country", filters={"code": country_code})[0]
		
		territory = frappe.get_all("Territory", filters={"name": country_code})
		if territory:
			territory_name = territory[0].name
		else:
			territory_name = "All Territories"

		address.update({
			"address_title": '%s %s' % (shipping_data.get("first_name"), shipping_data.get("last_name")),
			"contact_person": '%s %s' % (shipping_data.get("first_name"), shipping_data.get("last_name")),
			"address_line1": shipping_data.get("address1"),
			"address_line2": shipping_data.get("address2"),
			"address_type": "Shipping",
			"city": shipping_data.get("city"),
			"state": shipping_data.get("region"),
			"country": country.name,
			"pincode": shipping_data.get("postal_code"),
			"email_id": customer_data.get("email"),
			"phone": shipping_data.get("phone"),
			"territory": territory_name
		})

		address.set("links", [{"link_doctype": "Customer", "link_name": customer}])
		address.flags.ignore_permissions= True
		address.save()
