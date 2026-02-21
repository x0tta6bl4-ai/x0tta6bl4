package x0t

import (
	"context"
	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func Provider() *schema.Provider {
	return &schema.Provider{
		Schema: map[string]*schema.Schema{
			"api_url": {
				Type:        schema.TypeString,
				Optional:    true,
				DefaultFunc: schema.EnvDefaultFunc("X0T_API_URL", "http://localhost:8000/api/v1/maas"),
				Description: "The base URL for the x0tta6bl4 MaaS API.",
			},
			"api_key": {
				Type:        schema.TypeString,
				Required:    true,
				Sensitive:   true,
				DefaultFunc: schema.EnvDefaultFunc("X0T_API_KEY", nil),
				Description: "API Key for x0tta6bl4 authentication.",
			},
		},
		ResourcesMap: map[string]*schema.Resource{
			"x0t_mesh":       resourceMesh(),
			"x0t_acl_policy": resourceACLPolicy(),
		},
		DataSourcesMap: map[string]*schema.Resource{},
		ConfigureContextFunc: providerConfigure,
	}
}

type Client struct {
	ApiUrl string
	ApiKey string
}

func providerConfigure(ctx context.Context, d *schema.ResourceData) (interface{}, diag.Diagnostics) {
	apiUrl := d.Get("api_url").(string)
	apiKey := d.Get("api_key").(string)

	var diags diag.Diagnostics

	return &Client{
		ApiUrl: apiUrl,
		ApiKey: apiKey,
	}, diags
}
