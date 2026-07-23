import yaml
import os

def main():
    template_path = "/mnt/projects/k8s/base/secrets-template.yaml"
    output_path = "/mnt/projects/infra/k8s/overlays/staging/secrets.env"
    
    if not os.path.exists(template_path):
        print(f"Error: {template_path} not found")
        return
        
    with open(template_path, "r") as f:
        data = yaml.safe_load(f)
        
    string_data = data.get("stringData", {})
    
    with open(output_path, "w") as f:
        for key in sorted(string_data.keys()):
            f.write(f"{key}=mock_staging_value_for_{key.lower()}\n")
            
    print(f"Successfully generated {output_path} with {len(string_data)} keys.")

if __name__ == "__main__":
    main()
