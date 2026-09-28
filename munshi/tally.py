"""Tally-importable Sales Order vouchers.

Tally runs on-premise, and every installation names its ledgers and stock items
differently. So Munshi produces the XML file a Tally operator imports
(Gateway of Tally → Import → Vouchers); it does not post into Tally directly.
Stock item names are assumed to match the distributor's item master.
"""

from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape

from .catalog import BY_CODE


def sales_order_xml(order_no: str, party: str, when: datetime, lines: list[dict]) -> str:
    entries, total = [], 0.0
    for ln in lines:
        sku = BY_CODE[ln["sku"]]
        amount = round(sku.price * ln["units"], 2)
        total += amount
        entries.append(f"""      <ALLINVENTORYENTRIES.LIST>
        <STOCKITEMNAME>{escape(sku.name)}</STOCKITEMNAME>
        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
        <RATE>{sku.price:.2f}/pcs</RATE>
        <AMOUNT>{amount:.2f}</AMOUNT>
        <ACTUALQTY> {ln['units']} pcs</ACTUALQTY>
        <BILLEDQTY> {ln['units']} pcs</BILLEDQTY>
        <BATCHALLOCATIONS.LIST>
          <ORDERNO>{escape(order_no)}</ORDERNO>
          <AMOUNT>{amount:.2f}</AMOUNT>
          <ACTUALQTY> {ln['units']} pcs</ACTUALQTY>
          <BILLEDQTY> {ln['units']} pcs</BILLEDQTY>
        </BATCHALLOCATIONS.LIST>
      </ALLINVENTORYENTRIES.LIST>""")
    body = "\n".join(entries)
    return f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>
    <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
    <VOUCHER VCHTYPE="Sales Order" ACTION="Create">
      <DATE>{when:%Y%m%d}</DATE>
      <VOUCHERTYPENAME>Sales Order</VOUCHERTYPENAME>
      <VOUCHERNUMBER>{escape(order_no)}</VOUCHERNUMBER>
      <REFERENCE>{escape(order_no)}</REFERENCE>
      <PARTYLEDGERNAME>{escape(party)}</PARTYLEDGERNAME>
      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
      <NARRATION>WhatsApp order captured by Munshi</NARRATION>
{body}
      <LEDGERENTRIES.LIST>
        <LEDGERNAME>{escape(party)}</LEDGERNAME>
        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
        <AMOUNT>-{total:.2f}</AMOUNT>
      </LEDGERENTRIES.LIST>
    </VOUCHER>
    </TALLYMESSAGE></REQUESTDATA>
  </IMPORTDATA></BODY>
</ENVELOPE>
"""
