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

// KiloResponse represents the response from kilo CLI
type KiloResponse struct {
	Success bool        `json:"success"`
	Output  string      `json:"output"`
	Error   string      `json:"error,omitempty"`
	Result  interface{} `json:"result,omitempty"`
}

func main() {
	// Create MCP server
	s := server.NewMCPServer(
		"kilo-mcp",
		"1.0.0",
	)

	// Add tool for running kilo commands
	runTool := mcp.NewTool("run_kilo",
		mcp.WithDescription("Execute Kilo CLI commands for AI-powered code analysis and refactoring"),
		mcp.WithString("command",
			mcp.Required(),
			mcp.Description("The kilo command to execute (e.g., 'analyze', 'refactor', 'test')"),
		),
		mcp.WithString("args",
			mcp.Description("Additional arguments for the command"),
		),
		mcp.WithString("working_dir",
			mcp.Description("Working directory for the command"),
		),
	)

	s.AddTool(runTool, handleKiloCommand)

	// Add tool for analyzing code
	analyzeTool := mcp.NewTool("analyze_code",
		mcp.WithDescription("Analyze code quality and structure using Kilo"),
		mcp.WithString("file_path",
			mcp.Required(),
			mcp.Description("Path to the file or directory to analyze"),
		),
		mcp.WithString("analysis_type",
			mcp.Description("Type of analysis: 'quality', 'complexity', 'dependencies', 'security'"),
		),
		mcp.WithString("depth",
			mcp.Description("Analysis depth: 'shallow', 'medium', 'deep'"),
		),
	)

	s.AddTool(analyzeTool, handleAnalyzeCode)

	// Add tool for refactoring code
	refactorTool := mcp.NewTool("refactor_code",
		mcp.WithDescription("Refactor code using Kilo AI"),
		mcp.WithString("file_path",
			mcp.Required(),
			mcp.Description("Path to the file to refactor"),
		),
		mcp.WithString("refactor_type",
			mcp.Required(),
			mcp.Description("Type of refactoring: 'optimize', 'simplify', 'extract', 'rename'"),
		),
		mcp.WithString("scope",
			mcp.Description("Scope of refactoring: 'function', 'class', 'file', 'project'"),
		),
	)

	s.AddTool(refactorTool, handleRefactorCode)

	// Add tool for testing code
	testTool := mcp.NewTool("test_code",
		mcp.WithDescription("Run tests and generate test reports using Kilo"),
		mcp.WithString("test_path",
			mcp.Required(),
			mcp.Description("Path to test file or directory"),
		),
		mcp.WithString("test_type",
			mcp.Description("Type of tests: 'unit', 'integration', 'performance'"),
		),
		mcp.WithString("coverage",
			mcp.Description("Whether to generate coverage report (true/false)"),
		),
	)

	s.AddTool(testTool, handleTestCode)

	// Start the server
	if err := s.ServeStdio(); err != nil {
		log.Printf("Server error: %v", err)
	}
}

func handleKiloCommand(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	command := request.Params.Arguments["command"].(string)
	
	args := ""
	if a, ok := request.Params.Arguments["args"]; ok {
		args = a.(string)
	}
	
	workingDir := ""
	if wd, ok := request.Params.Arguments["working_dir"]; ok {
		workingDir = wd.(string)
	}

	// Build the kilo command
	var cmd *exec.Cmd
	if workingDir != "" {
		cmd = exec.CommandContext(ctx, "kilo", command, args)
		cmd.Dir = workingDir
	} else {
		cmd = exec.CommandContext(ctx, "kilo", command, args)
	}

	// Execute the command
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Kilo command failed: %v\nOutput: %s", err, string(output))), nil
	}

	// Parse and return the result
	result := map[string]interface{}{
		"success": true,
		"output":  string(output),
	}

	resultJSON, _ := json.Marshal(result)
	return mcp.NewToolResultText(string(resultJSON)), nil
}

func handleAnalyzeCode(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	filePath := request.Params.Arguments["file_path"].(string)
	
	analysisType := "quality"
	if a, ok := request.Params.Arguments["analysis_type"]; ok {
		analysisType = a.(string)
	}
	
	depth := "medium"
	if d, ok := request.Params.Arguments["depth"]; ok {
		depth = d.(string)
	}

	// Verify file exists
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return mcp.NewToolResultError(fmt.Sprintf("Path does not exist: %s", filePath)), nil
	}

	// Build the analyze command
	args := []string{"analyze", "--path", filePath, "--type", analysisType, "--depth", depth}

	cmd := exec.CommandContext(ctx, "kilo", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Code analysis failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}

func handleRefactorCode(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	filePath := request.Params.Arguments["file_path"].(string)
	refactorType := request.Params.Arguments["refactor_type"].(string)
	
	scope := "function"
	if s, ok := request.Params.Arguments["scope"]; ok {
		scope = s.(string)
	}

	// Verify file exists
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return mcp.NewToolResultError(fmt.Sprintf("File does not exist: %s", filePath)), nil
	}

	// Build the refactor command
	args := []string{"refactor", "--file", filePath, "--type", refactorType, "--scope", scope}

	cmd := exec.CommandContext(ctx, "kilo", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Code refactoring failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}

func handleTestCode(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	testPath := request.Params.Arguments["test_path"].(string)
	
	testType := "unit"
	if t, ok := request.Params.Arguments["test_type"]; ok {
		testType = t.(string)
	}
	
	coverage := "true"
	if c, ok := request.Params.Arguments["coverage"]; ok {
		coverage = c.(string)
	}

	// Build the test command
	args := []string{"test", "--path", testPath, "--type", testType}
	if coverage == "true" {
		args = append(args, "--coverage")
	}

	cmd := exec.CommandContext(ctx, "kilo", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Testing failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}