package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

// OpenCodeResponse represents the response from opencode CLI
type OpenCodeResponse struct {
	Success bool        `json:"success"`
	Output  string      `json:"output"`
	Error   string      `json:"error,omitempty"`
	Result  interface{} `json:"result,omitempty"`
}

func main() {
	// Create MCP server
	s := server.NewMCPServer(
		"opencode-mcp",
		"1.0.0",
	)

	// Add tool for running opencode commands
	runTool := mcp.NewTool("run_opencode",
		mcp.WithDescription("Execute OpenCode CLI commands for AI-powered code generation and editing"),
		mcp.WithString("command",
			mcp.Required(),
			mcp.Description("The opencode command to execute (e.g., 'generate', 'edit', 'explain')"),
		),
		mcp.WithString("args",
			mcp.Description("Additional arguments for the command"),
		),
		mcp.WithString("working_dir",
			mcp.Description("Working directory for the command"),
		),
	)

	s.AddTool(runTool, handleOpenCodeCommand)

	// Add tool for generating code
	generateTool := mcp.NewTool("generate_code",
		mcp.WithDescription("Generate code using OpenCode AI"),
		mcp.WithString("prompt",
			mcp.Required(),
			mcp.Description("Description of the code to generate"),
		),
		mcp.WithString("language",
			mcp.Description("Programming language (e.g., 'python', 'javascript', 'go')"),
		),
		mcp.WithString("context",
			mcp.Description("Additional context or requirements"),
		),
	)

	s.AddTool(generateTool, handleGenerateCode)

	// Add tool for editing code
	editTool := mcp.NewTool("edit_code",
		mcp.WithDescription("Edit existing code using OpenCode AI"),
		mcp.WithString("file_path",
			mcp.Required(),
			mcp.Description("Path to the file to edit"),
		),
		mcp.WithString("instructions",
			mcp.Required(),
			mcp.Description("Instructions for how to edit the code"),
		),
		mcp.WithString("backup",
			mcp.Description("Whether to create a backup (true/false)"),
		),
	)

	s.AddTool(editTool, handleEditCode)

	// Add tool for explaining code
	explainTool := mcp.NewTool("explain_code",
		mcp.WithDescription("Explain code using OpenCode AI"),
		mcp.WithString("code",
			mcp.Required(),
			mcp.Description("The code to explain"),
		),
		mcp.WithString("language",
			mcp.Description("Programming language of the code"),
		),
		mcp.WithString("detail_level",
			mcp.Description("Level of detail: 'brief', 'detailed', 'expert'"),
		),
	)

	s.AddTool(explainTool, handleExplainCode)

	// Start the server
	if err := s.ServeStdio(); err != nil {
		log.Printf("Server error: %v", err)
	}
}

func handleOpenCodeCommand(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	command := request.Params.Arguments["command"].(string)
	
	args := ""
	if a, ok := request.Params.Arguments["args"]; ok {
		args = a.(string)
	}
	
	workingDir := ""
	if wd, ok := request.Params.Arguments["working_dir"]; ok {
		workingDir = wd.(string)
	}

	// Build the opencode command
	var cmd *exec.Cmd
	if workingDir != "" {
		cmd = exec.CommandContext(ctx, "opencode", command, args)
		cmd.Dir = workingDir
	} else {
		cmd = exec.CommandContext(ctx, "opencode", command, args)
	}

	// Execute the command
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("OpenCode command failed: %v\nOutput: %s", err, string(output))), nil
	}

	// Parse and return the result
	result := OpenCodeResponse{
		Success: true,
		Output:  string(output),
	}

	resultJSON, _ := json.Marshal(result)
	return mcp.NewToolResultText(string(resultJSON)), nil
}

func handleGenerateCode(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	prompt := request.Params.Arguments["prompt"].(string)
	
	language := "python"
	if l, ok := request.Params.Arguments["language"]; ok {
		language = l.(string)
	}
	
	context := ""
	if c, ok := request.Params.Arguments["context"]; ok {
		context = c.(string)
	}

	// Build the generate command
	args := []string{"generate", "--prompt", prompt, "--language", language}
	if context != "" {
		args = append(args, "--context", context)
	}

	cmd := exec.CommandContext(ctx, "opencode", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Code generation failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}

func handleEditCode(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	filePath := request.Params.Arguments["file_path"].(string)
	instructions := request.Params.Arguments["instructions"].(string)
	
	backup := "true"
	if b, ok := request.Params.Arguments["backup"]; ok {
		backup = b.(string)
	}

	// Verify file exists
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return mcp.NewToolResultError(fmt.Sprintf("File does not exist: %s", filePath)), nil
	}

	// Build the edit command
	args := []string{"edit", "--file", filePath, "--instructions", instructions}
	if backup == "true" {
		args = append(args, "--backup")
	}

	cmd := exec.CommandContext(ctx, "opencode", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Code editing failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}

func handleExplainCode(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	code := request.Params.Arguments["code"].(string)
	
	language := ""
	if l, ok := request.Params.Arguments["language"]; ok {
		language = l.(string)
	}
	
	detailLevel := "detailed"
	if d, ok := request.Params.Arguments["detail_level"]; ok {
		detailLevel = d.(string)
	}

	// Build the explain command
	args := []string{"explain", "--code", code}
	if language != "" {
		args = append(args, "--language", language)
	}
	args = append(args, "--detail", detailLevel)

	cmd := exec.CommandContext(ctx, "opencode", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Code explanation failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}