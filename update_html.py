import re

html_path = 'index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Payment Options HTML to insert after </form>
payment_options_template = """
                    <div class="payment-section">
                        <p class="payment-label">Forma de Pagamento:</p>
                        <div class="payment-methods-grid">
                            <label class="payment-method-card selected">
                                <input type="radio" name="payment_method_{PRODUCT}" value="pix" checked>
                                <div class="method-icon"><img src="https://logospng.org/download/pix/logo-pix-icone-512.png" alt="Pix"></div>
                                <span>Pix (Instantâneo)</span>
                            </label>
                            <label class="payment-method-card">
                                <input type="radio" name="payment_method_{PRODUCT}" value="card">
                                <div class="method-icon"><i class="fas fa-credit-card" style="color: white;"></i></div>
                                <span>Cartão / Outros</span>
                            </label>
                        </div>
                    </div>
"""

# Pix Result HTML to insert after the button
pix_result_template = """
                <div class="pix-result-container" style="display: none;">
                    <p style="color: #4cd137; font-weight: bold; margin-bottom: 10px;">QR Code Gerado!</p>
                    <div class="pix-qr-wrapper">
                        <img class="pix-qr-img" src="" alt="QR Code Pix">
                    </div>
                    <div class="pix-copy-paste">
                        <input type="text" class="pix-code-input" readonly>
                        <button class="btn-copy-pix">COPIAR</button>
                    </div>
                    <p class="pix-instructions">Abra o app do seu banco e escaneie o QR Code ou use o Pix Copia e Cola.</p>
                </div>
"""

# We need to target each modal specifically to inject the correct product name in the radio name
products = ['LORD', 'KNIGHT', 'GUARDIAN', 'CHAMPION']

# Regex to match the modal block for each product
# We look for the data-product attribute to identify the block
for product in products:
    print(f"Processing {product}...")
    
    # 1. Insert Payment Options after </form>
    # We find the specific form for this product. 
    # The structure is: <h2 ... data-product="PRODUCT"> ... <form ...> </form>
    
    # Construct a regex that finds the specific form closing tag for this product
    # We use a lookbehind or just match the whole block?
    # Simpler: Find the index of data-product="PRODUCT"
    
    product_marker = f'data-product="{product}"'
    marker_index = content.find(product_marker)
    
    if marker_index == -1:
        print(f"Could not find marker for {product}")
        continue
        
    # Find the next </form> after this marker
    form_close_index = content.find('</form>', marker_index)
    if form_close_index == -1:
        print(f"Could not find </form> for {product}")
        continue
        
    # Check if we already added it (avoid double insertion)
    # Check if "payment-section" is present shortly after
    chunk_after = content[form_close_index:form_close_index+200]
    if "payment-section" in chunk_after:
        print(f"Payment section already exists for {product}")
    else:
        # Insert payment options
        insertion = payment_options_template.replace('{PRODUCT}', product)
        content = content[:form_close_index + 7] + insertion + content[form_close_index + 7:]
        print(f"Inserted payment options for {product}")

    # Re-calculate indices because content changed
    marker_index = content.find(product_marker)
    
    # 2. Insert Pix Result after Button
    # Find the button after the marker
    # <button type="button" class="origin-btn btn-buy checkout-btn" ...>ADQUIRIR AGORA ➜</button>
    
    button_marker = 'ADQUIRIR AGORA ➜</button>'
    button_index = content.find(button_marker, marker_index)
    
    if button_index == -1:
        print(f"Could not find button for {product}")
        continue
        
    button_end_index = button_index + len(button_marker)
    
    # Check if already added
    chunk_after_btn = content[button_end_index:button_end_index+200]
    if "pix-result-container" in chunk_after_btn:
        print(f"Pix result already exists for {product}")
    else:
        content = content[:button_end_index] + pix_result_template + content[button_end_index:]
        print(f"Inserted Pix result for {product}")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done updating index.html")
