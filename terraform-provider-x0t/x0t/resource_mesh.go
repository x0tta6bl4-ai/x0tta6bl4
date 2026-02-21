package x0t

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"
	"time"

	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceMesh() *schema.Resource {
	return &schema.Resource{
		CreateContext: resourceMeshCreate,
		ReadContext:   resourceMeshRead,
		UpdateContext: resourceMeshUpdate,
		DeleteContext: resourceMeshDelete,
		Schema: map[string]*schema.Schema{
			"name": {
				Type:     schema.TypeString,
				Required: true,
			},
			"nodes": {
				Type:     schema.TypeInt,
				Optional: true,
				Default:  5,
			},
			"plan": {
				Type:     schema.TypeString,
				Optional: true,
				Default:  "starter",
			},
			"pqc_enabled": {
				Type:     schema.TypeBool,
				Optional: true,
				Default:  true,
			},
			"mesh_id": {
				Type:     schema.TypeString,
				Computed: true,
			},
			"status": {
				Type:     schema.TypeString,
				Computed: true,
			},
		},
	}
}

func resourceMeshCreate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	c := m.(*Client)
	var diags diag.Diagnostics

	payload := map[string]interface{}{
		"name":         d.Get("name").(string),
		"nodes":        d.Get("nodes").(int),
		"billing_plan": d.Get("plan").(string),
		"pqc_enabled":  d.Get("pqc_enabled").(bool),
	}
	
	buf, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", fmt.Sprintf("%s/deploy", c.ApiUrl), strings.NewReader(string(buf)))
	req.Header.Set("X-API-Key", c.ApiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return diag.FromErr(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := ioutil.ReadAll(resp.Body)
		return diag.Errorf("API error: %s", body)
	}

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	d.SetId(result["mesh_id"].(string))
	d.Set("mesh_id", result["mesh_id"].(string))
	d.Set("status", result["status"].(string))

	return diags
}

func resourceMeshRead(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	c := m.(*Client)
	var diags diag.Diagnostics

	meshId := d.Id()
	req, _ := http.NewRequest("GET", fmt.Sprintf("%s/%s/status", c.ApiUrl, meshId), nil)
	req.Header.Set("X-API-Key", c.ApiKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return diag.FromErr(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		d.SetId("")
		return diags
	}

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	d.Set("status", result["status"].(string))
	d.Set("nodes", result["nodes_total"].(int))

	return diags
}

func resourceMeshUpdate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	// Implementation for scaling (POST /{id}/scale)
	return resourceMeshRead(ctx, d, m)
}

func resourceMeshDelete(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	c := m.(*Client)
	var diags diag.Diagnostics

	meshId := d.Id()
	req, _ := http.NewRequest("DELETE", fmt.Sprintf("%s/%s", c.ApiUrl, meshId), nil)
	req.Header.Set("X-API-Key", c.ApiKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return diag.FromErr(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNotFound {
		return diag.Errorf("Failed to delete mesh: %d", resp.StatusCode)
	}

	d.SetId("")
	return diags
}
