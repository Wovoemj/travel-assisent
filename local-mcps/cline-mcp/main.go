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

// ClineResponse represents the response from cline CLI
type ClineResponse struct {
	Success bool        `json:"success"`
	Output  string      `json:"output"`
	Error   string      `json:"error,omitempty"`
	Result  interface{} `json:"result,omitempty"`
}

func main() {
	// Create MCP server
	s := server.NewMCPServer(
		"cline-mcp",
		"1.0.0",
	)

	// Add tool for running cline commands
	runTool := mcp.NewTool("run_cline",
		mcp.WithDescription("Execute Cline CLI commands for AI-powered code completion and assistance"),
		mcp.WithString("command",
			mcp.Required(),
			mcp.Description("The cline command to execute (e.g., 'complete', 'suggest', 'chat')"),
		),
		mcp.WithString("args",
			mcp.Description("Additional arguments for the command"),
		),
		mcp.WithString("working_dir",
			mcp.Description("Working directory for the command"),
		),
	)

	s.AddTool(runTool, handleClineCommand)

	// Add tool for code completion
	completeTool := mcp.NewTool("complete_code",
		mcp.WithDescription("Get AI-powered code completions using Cline"),
		mcp.WithString("code",
			mcp.Required(),
			mcp.Description("The code context for completion"),
		),
		mcp.WithString("language",
			mcp.Description("Programming language (e.g., 'python', 'javascript', 'go')"),
		),
		mcp.WithString("completion_type",
			mcp.Description("Type of completion: 'function', 'class', 'variable', 'import'"),
		),
	)

	s.AddTool(completeTool, handleCodeCompletion)

	// Add tool for code suggestions
	suggestTool := mcp.NewTool("suggest_improvements",
		mcp.WithDescription("Get AI suggestions for code improvements using Cline"),
		mcp.WithString("file_path",
			mcp.Required(),
			mcp.Description("Path to the file to analyze"),
		),
		mcp.WithString("focus_area",
			mcp.Description("Area to focus on: 'performance', 'readability', 'security', 'best_practices'"),
		),
		mcp.WithString("language",
			mcp.Description("Programming language of the file"),
		),
	)

	s.AddTool(suggestTool, handleSuggestions)

	// Add tool for chat assistance
	chatTool := mcp.NewTool("chat_assistance",
		mcp.WithDescription("Get AI coding assistance through chat using Cline"),
		mcp.WithString("message",
			mcp.Required(),
			mcp.Description("Your coding question or request"),
		),
		mcp.WithString("context",
			mcp.Description("Additional code context"),
		),
		mcp.WithString("language",
			mcp.Description("Programming language context"),
		),
	)

	s.AddTool(chatTool, handleChatAssistance)

	// Start the server
	if err := s.ServeStdio(); err != nil {
		log.Printf("Server error: %v", err)
	}
}

func handleClineCommand(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	command := request.Params.Arguments["command"].(string)
	
	args := ""
	if a, ok := request.Params.Arguments["args"]; ok {
		args = a.(string)
	}
	
	workingDir := ""
	if wd, ok := request.Params.Arguments["working_dir"]; ok {
		workingDir = wd.(string)
	}

	// Build the cline command
	var cmd *exec.Cmd
	if workingDir != "" {
		cmd = exec.CommandContext(ctx, "cline", command, args)
		cmd.Dir = workingDir
	} else {
		cmd = exec.CommandContext(ctx, "cline", command, args)
	}

	// Execute the command
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Cline command failed: %v\nOutput: %s", err, string(output))), nil
	}

	// Parse and return the result
	result := ClineResponse{
		Success: true,
		Output:  string(output),
	}

	resultJSON, _ := json.Marshal(result)
	return mcp.NewToolResultText(string(resultJSON)), nil
}

func handleCodeCompletion(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	code := request.Params.Arguments["code"].(string)
	
	language := "python"
	if l, ok := request.Params.Arguments["language"]; ok {
		language = l.(string)
	}
	
	completionType := "function"
	if c, ok := request.Params.Arguments["completion_type"]; ok {
		completionType = c.(string)
	}

	// Build the complete command
	args := []string{"complete", "--code", code, "--language", language, "--type", completionType}

	cmd := exec.CommandContext(ctx, "cline", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Code completion failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}

func handleSuggestions(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	filePath := request.Params.Arguments["file_path"].(string)
	
	focusArea := "readability"
	if f, ok := request.Params.Arguments["focus_area"]; ok {
		focusArea = f.(string)
	}
	
	language := ""
	if l, ok := request.Params.Arguments["language"]; ok {
		language = l.(string)
	}

	// Verify file exists
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return mcp.NewToolResultError(fmt.Sprintf("File does not exist: %s", filePath)), nil
	}

	// Build the suggest command
	args := []string{"suggest", "--file", filePath, "--focus", focusArea}
	if language != "" {
		args = append(args, "--language", language)
	}

	cmd := exec.CommandContext(ctx, "cline", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Suggestions failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}

func handleChatAssistance(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	message := request.Params.Arguments["message"].(string)
	
	contextStr := ""
	if c, ok := request.Params.Arguments["context"]; ok {
		contextStr = c.(string)
	}
	
	language := ""
	if l, ok := request.Params.Arguments["language"]; ok {
		language = l.(string)
	}

	// Build the chat command
	args := []string{"chat", "--message", message}
	if contextStr != "" {
		args = append(args, "--context", contextStr)
	}
	if language != "" {
		args = append(args, "--language", language)
	}

	cmd := exec.CommandContext(ctx, "cline", args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("Chat assistance failed: %v", err)), nil
	}

	return mcp.NewToolResultText(string(output)), nil
}