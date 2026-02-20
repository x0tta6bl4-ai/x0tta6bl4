package main

import (
	"github.com/hashicorp/terraform-plugin-sdk/v2/plugin"
	"github.com/x0tta6bl4/terraform-provider-x0t/x0t"
)

func main() {
	plugin.Serve(&plugin.ServeOpts{
		ProviderFunc: x0t.Provider,
	})
}
