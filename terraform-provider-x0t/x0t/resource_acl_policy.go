package x0t

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/hashicorp/terraform-plugin-sdk/v2/diag"
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

func resourceACLPolicy() *schema.Resource {
	return &schema.Resource{
		CreateContext: resourceACLPolicyCreate,
		ReadContext:   resourceACLPolicyRead,
		DeleteContext: resourceACLPolicyDelete,
		Schema: map[string]*schema.Schema{
			"mesh_id": {
				Type:     schema.TypeString,
				Required: true,
				ForceNew: true,
			},
			"source_tag": {
				Type:     schema.TypeString,
				Required: true,
				ForceNew: true,
			},
			"target_tag": {
				Type:     schema.TypeString,
				Required: true,
				ForceNew: true,
			},
			"action": {
				Type:     schema.TypeString,
				Optional: true,
				Default:  "allow",
			},
			"policy_id": {
				Type:     schema.TypeString,
				Computed: true,
			},
		},
	}
}

func resourceACLPolicyCreate(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	c := m.(*Client)
	meshId := d.Get("mesh_id").(string)

	payload := map[string]interface{}{
		"source_tag": d.Get("source_tag").(string),
		"target_tag": d.Get("target_tag").(string),
		"action":     d.Get("action").(string),
	}

	buf, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", fmt.Sprintf("%s/%s/policies", c.ApiUrl, meshId), strings.NewReader(string(buf)))
	req.Header.Set("X-API-Key", c.ApiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return diag.FromErr(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return diag.Errorf("API error: status %d", resp.StatusCode)
	}

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	d.SetId(result["id"].(string))
	d.Set("policy_id", result["id"].(string))

	return nil
}

func resourceACLPolicyRead(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	c := m.(*Client)
	meshId := d.Get("mesh_id").(string)
	policyId := d.Id()

	req, _ := http.NewRequest("GET", fmt.Sprintf("%s/%s/policies", c.ApiUrl, meshId), nil)
	req.Header.Set("X-API-Key", c.ApiKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return diag.FromErr(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return diag.Errorf("Failed to read policies: %d", resp.StatusCode)
	}

	var policies []map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&policies)

	found := false
	for _, p := range policies {
		if p["id"].(string) == policyId {
			d.Set("source_tag", p["source_tag"])
			d.Set("target_tag", p["target_tag"])
			d.Set("action", p["action"])
			found = true
			break
		}
	}

	if !found {
		d.SetId("")
	}

	return nil
}

func resourceACLPolicyDelete(ctx context.Context, d *schema.ResourceData, m interface{}) diag.Diagnostics {
	c := m.(*Client)
	meshId := d.Get("mesh_id").(string)
	policyId := d.Id()

	req, _ := http.NewRequest("DELETE", fmt.Sprintf("%s/%s/policies/%s", c.ApiUrl, meshId, policyId), nil)
	req.Header.Set("X-API-Key", c.ApiKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return diag.FromErr(err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNotFound {
		return diag.Errorf("Failed to delete policy: %d", resp.StatusCode)
	}

	d.SetId("")
	return nil
}
