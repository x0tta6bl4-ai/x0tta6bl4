package actuator

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// AILogic defines the interface for interacting with the LLM.
type AILogic interface {
	AnalyzeState(ctx context.Context, systemState SystemDump) (*ActionPlan, error)
}

// GeminiBrain uses the Google Gemini API directly via HTTP.
type GeminiBrain struct {
	APIKey string
	Model  string
}

func NewGeminiBrain() *GeminiBrain {
	return &GeminiBrain{
		APIKey: os.Getenv("GEMINI_API_KEY"),
		Model:  "gemini-1.5-flash", // Defaulting to flash for faster self-healing
	}
}

type geminiRequest struct {
	Contents []struct {
		Parts []struct {
			Text string `json:"text"`
		} `json:"parts"`
	} `json:"contents"`
	GenerationConfig struct {
		ResponseMimeType string `json:"response_mime_type"`
	} `json:"generationConfig"`
}

type geminiResponse struct {
	Candidates []struct {
		Content struct {
			Parts []struct {
				Text string `json:"text"`
			} `json:"parts"`
		} `json:"content"`
	} `json:"candidates"`
}

func (b *GeminiBrain) AnalyzeState(ctx context.Context, systemState SystemDump) (*ActionPlan, error) {
	if b.APIKey == "" {
		return nil, fmt.Errorf("GEMINI_API_KEY environment variable is not set")
	}

	prompt := fmt.Sprintf(`Analyze system failure on Ubuntu 24.04.
Component: %s

Journal Logs:
%s

Dmesg:
%s

Metrics:
%v

You MUST respond strictly in the following JSON format:
{
  "diagnosis": "string explaining the issue",
  "actions": [
    {
      "command": "restart_service",
      "target": "v2ray.service"
    }
  ]
}

Allowed commands: "restart_service", "patch_config".
Allowed targets: "x-ui.service", "ghost-vpn.service", "/usr/local/etc/xray/config.json", "/usr/local/x-ui/bin/config.json".
`, systemState.FailedComponent, strings.Join(systemState.JournalLogs, "\n"), strings.Join(systemState.DmesgLogs, "\n"), systemState.Metrics)

	reqBody := geminiRequest{}
	reqBody.Contents = append(reqBody.Contents, struct {
		Parts []struct {
			Text string `json:"text"`
		} `json:"parts"`
	}{
		Parts: []struct {
			Text string `json:"text"`
		}{{Text: prompt}},
	})
	reqBody.GenerationConfig.ResponseMimeType = "application/json"

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, err
	}

	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", b.Model, b.APIKey)

	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Gemini API call failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Gemini API returned error %d: %s", resp.StatusCode, string(body))
	}

	var geminiResp geminiResponse
	if err := json.NewDecoder(resp.Body).Decode(&geminiResp); err != nil {
		return nil, fmt.Errorf("failed to decode Gemini response: %w", err)
	}

	if len(geminiResp.Candidates) == 0 || len(geminiResp.Candidates[0].Content.Parts) == 0 {
		return nil, fmt.Errorf("Gemini API returned empty response")
	}

	rawJSON := geminiResp.Candidates[0].Content.Parts[0].Text
	var plan ActionPlan
	if err := json.Unmarshal([]byte(rawJSON), &plan); err != nil {
		return nil, fmt.Errorf("failed to parse AI response JSON: %w. Raw content: %s", err, rawJSON)
	}

	return &plan, nil
}

// MockBrain is a fake implementation for testing the safe execution pipeline.
type MockBrain struct {
	MockResponseJSON string
}

func NewMockBrain(responseJSON string) *MockBrain {
	return &MockBrain{MockResponseJSON: responseJSON}
}

func (b *MockBrain) AnalyzeState(ctx context.Context, systemState SystemDump) (*ActionPlan, error) {
	fmt.Printf("[MockBrain] Analyzing state for component: %s\n", systemState.FailedComponent)

	var plan ActionPlan
	if err := json.Unmarshal([]byte(b.MockResponseJSON), &plan); err != nil {
		return nil, fmt.Errorf("failed to parse mock response: %w", err)
	}

	return &plan, nil
}

