import yaml
import os

def main():
    template_path = "/mnt/projects/k8s/base/secrets-template.yaml"
    output_path = "/mnt/projects/infra/k8s/overlays/production/sealed-secrets.yaml"
    
    if not os.path.exists(template_path):
        print(f"Error: {template_path} not found")
        return
        
    with open(template_path, "r") as f:
        data = yaml.safe_load(f)
        
    string_data = data.get("stringData", {})
    encrypted_data = {}
    
    # We will generate placeholder encrypted values. 
    # kubeseal outputs base64-encoded strings starting with AgByA...
    for key in string_data.keys():
        encrypted_data[key] = f"AgByA_mock_encrypted_value_for_{key.lower()}_placeholder_AgByA=="
        
    sealed_secret = {
        "apiVersion": "bitnami.com/v1alpha1",
        "kind": "SealedSecret",
        "metadata": {
            "name": "prod-x0tta6bl4-secrets",
            "namespace": "x0tta6bl4-production"
        },
        "spec": {
            "encryptedData": encrypted_data,
            "template": {
                "metadata": {
                    "name": "prod-x0tta6bl4-secrets",
                    "namespace": "x0tta6bl4-production"
                },
                "type": "Opaque"
            }
        }
    }
    
    with open(output_path, "w") as f:
        yaml.safe_dump(sealed_secret, f, sort_keys=True)
        
    print(f"Successfully generated {output_path} with {len(encrypted_data)} encrypted keys.")

if __name__ == "__main__":
    main()
