using System;
using System.Collections.Generic;
using System.IO;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.Formatting;
using Microsoft.CodeAnalysis.MSBuild; // if needed for workspace creation

namespace MethodInjector
{
    class Program
    {
        static int Main(string[] args)
        {
            if (args.Length != 1)
            {
                Console.WriteLine("Usage: dotnet run -- <directory_path>");
                return 1;
            }

            string directoryPath = args[0];

            if (!Directory.Exists(directoryPath))
            {
                Console.WriteLine($"Directory not found: {directoryPath}");
                return 1;
            }

            // Find all .cs files in the directory
            string[] csFiles = Directory.GetFiles(directoryPath, "*.cs", SearchOption.AllFiles);

            if (csFiles.Length == 0)
            {
                Console.WriteLine($"No .cs files found in {directoryPath}");
                return 1;
            }

            Console.WriteLine($"Found {csFiles.Length} .cs files to process");

            foreach (string filePath in csFiles)
            {
                Console.WriteLine($"Processing: {filePath}");
                // Call the processing method for each file
                ProcessCsFile(filePath);
            }

            return 0;
        }

        // Create a method to process individual files
        static void ProcessCsFile(string filePath)
        {
            string code = File.ReadAllText(filePath);
            SyntaxTree tree = CSharpSyntaxTree.ParseText(code);
            SyntaxNode root = tree.GetRoot();

            // Check if "using System;" is present and add it if not
            bool hasSystemNamespace = false;
            foreach (var directive in root.DescendantNodes().OfType<UsingDirectiveSyntax>())
            {
                if (directive.Name.ToString() == "System" && directive.StaticKeyword.IsKind(SyntaxKind.None))
                {
                    hasSystemNamespace = true;
                    break;
                }
            }

            if (!hasSystemNamespace)
            {
                var systemUsing = SyntaxFactory.UsingDirective(SyntaxFactory.ParseName("System"));
                var compilationUnit = (CompilationUnitSyntax)root;
                root = compilationUnit.AddUsings(systemUsing);
            }

            // Create our rewriter to inject logging into methods and constructors.
            var rewriter = new MethodInjectorRewriter();
            SyntaxNode newRoot = rewriter.Visit(root);

            // Optionally, format the new syntax tree for a cleaner output.
            using (var workspace = new AdhocWorkspace())
            {
                newRoot = Formatter.Format(newRoot, workspace);
            }

            File.WriteAllText(filePath, newRoot.ToFullString());
            Console.WriteLine($"Modified file written to: {filePath}");
        }
    }

    /// <summary>
    /// Rewrites method and constructor bodies by injecting a logging statement at the start
    /// and an exit log before every return as well as at the end of the method.
    /// It also converts expression-bodied members to block bodies.
    /// </summary>
    class MethodInjectorRewriter : CSharpSyntaxRewriter
    {
        // A stack to keep track of the current method name.
        private readonly Stack<string> methodNameStack = new Stack<string>();
        // Track the current namespace and class name
        private string currentNamespace = string.Empty;
        private string currentClass = string.Empty;

        public override SyntaxNode VisitNamespaceDeclaration(NamespaceDeclarationSyntax node)
        {
            string previousNamespace = currentNamespace;
            currentNamespace = node.Name.ToString();
            
            var result = base.VisitNamespaceDeclaration(node);
            
            currentNamespace = previousNamespace;
            return result;
        }

        public override SyntaxNode VisitClassDeclaration(ClassDeclarationSyntax node)
        {
            string previousClass = currentClass;
            currentClass = node.Identifier.Text;
            
            var result = base.VisitClassDeclaration(node);
            
            currentClass = previousClass;
            return result;
        }

        public override SyntaxNode VisitMethodDeclaration(MethodDeclarationSyntax node)
        {
            string methodName = node.Identifier.Text;
            methodNameStack.Push(methodName);

            BlockSyntax newBody = null;

            if (node.Body != null)
            {
                // For methods with a block body.
                newBody = ProcessBlock(node.Body, methodName);
            }
            else if (node.ExpressionBody != null)
            {
                // For expression-bodied methods, convert them to a block body.
                newBody = ConvertExpressionBodyToBlock(node.ExpressionBody, methodName, node.ReturnType);
            }

            methodNameStack.Pop();

            if (newBody != null)
            {
                // Replace the original body with our new body.
                var newNode = node.WithBody(newBody)
                                  .WithExpressionBody(null)
                                  .WithSemicolonToken(SyntaxFactory.Token(SyntaxKind.None));
                return base.VisitMethodDeclaration(newNode);
            }

            return base.VisitMethodDeclaration(node);
        }

        public override SyntaxNode VisitConstructorDeclaration(ConstructorDeclarationSyntax node)
        {
            // Simply return the base visit without injecting any logging code
            return base.VisitConstructorDeclaration(node);
        }

        /// <summary>
        /// Processes a block by injecting an entry log at the beginning,
        /// an exit log at the end, and rewriting every return statement to include an exit log.
        /// </summary>
        private BlockSyntax ProcessBlock(BlockSyntax block, string methodName)
        {
            // Create the entry and exit log statements.
            var entryLog = CreateLogStatement($"AXAL_ENTER {GetFullClassPath()} {methodName} {{DateTime.Now.ToString(\"yyyy-MM-dd HH:mm:ss.ffffff\")}}", true);
            var exitLog = CreateLogStatement($"AXAL_EXIT {GetFullClassPath()} {methodName} {{DateTime.Now.ToString(\"yyyy-MM-dd HH:mm:ss.ffffff\")}}", false);

            // First, rewrite return statements to include the exit log.
            var processedBlock = (BlockSyntax)new ReturnInjector(methodName, GetFullClassPath()).Visit(block);

            // Then, insert the entry log at the very beginning and the exit log at the end.
            var newStatements = new List<StatementSyntax>
            {
                entryLog
            };
            newStatements.AddRange(processedBlock.Statements);
            newStatements.Add(exitLog);

            return SyntaxFactory.Block(newStatements);
        }

        /// <summary>
        /// Get the full class path including namespace
        /// </summary>
        private string GetFullClassPath()
        {
            if (string.IsNullOrEmpty(currentNamespace))
                return currentClass;
            
            return $"{currentNamespace}.{currentClass}";
        }

        /// <summary>
        /// Converts an expression-bodied member to a block body, injecting logging statements.
        /// </summary>
        private BlockSyntax ConvertExpressionBodyToBlock(ArrowExpressionClauseSyntax expressionBody, string methodName, TypeSyntax returnType)
        {
            var entryLog = CreateLogStatement($"AXAL_ENTER {GetFullClassPath()} {methodName} {{DateTime.Now.ToString(\"yyyy-MM-dd HH:mm:ss.ffffff\")}}", true);
            var exitLog = CreateLogStatement($"AXAL_EXIT {GetFullClassPath()} {methodName} {{DateTime.Now.ToString(\"yyyy-MM-dd HH:mm:ss.ffffff\")}}", false);

            // Determine if the method is void.
            bool isVoid = returnType.ToString().Equals("void", StringComparison.OrdinalIgnoreCase);

            if (isVoid)
            {
                // For void methods, simply treat the expression as a statement.
                var exprStatement = SyntaxFactory.ExpressionStatement(expressionBody.Expression);
                return SyntaxFactory.Block(entryLog, exprStatement, exitLog);
            }
            else
            {
                // For non-void methods, assign the expression to a temporary variable and return it.
                // Using a name unlikely to clash.
                var tempVarName = "__result";
                var declaration = SyntaxFactory.LocalDeclarationStatement(
                    SyntaxFactory.VariableDeclaration(returnType)
                    .WithVariables(
                        SyntaxFactory.SingletonSeparatedList(
                            SyntaxFactory.VariableDeclarator(SyntaxFactory.Identifier(tempVarName))
                                         .WithInitializer(SyntaxFactory.EqualsValueClause(expressionBody.Expression))
                        )
                    )
                );

                var returnStatement = SyntaxFactory.ReturnStatement(SyntaxFactory.IdentifierName(tempVarName));

                return SyntaxFactory.Block(entryLog, declaration, exitLog, returnStatement);
            }
        }

        /// <summary>
        /// Helper method to create a Console.WriteLine statement for a given message.
        /// </summary>
        private ExpressionStatementSyntax CreateLogStatement(string message, bool isEnter)
        {
            // We need to use string interpolation for the DateTime.Now
            var interpolatedString = SyntaxFactory.InterpolatedStringExpression(
                SyntaxFactory.Token(SyntaxKind.InterpolatedStringStartToken),
                SyntaxFactory.List<InterpolatedStringContentSyntax>()
                    .Add(SyntaxFactory.InterpolatedStringText(
                        SyntaxFactory.Token(
                            SyntaxFactory.TriviaList(),
                            SyntaxKind.InterpolatedStringTextToken,
                            message,
                            message,
                            SyntaxFactory.TriviaList()
                        )
                    ))
            );

            return SyntaxFactory.ExpressionStatement(
                SyntaxFactory.InvocationExpression(
                    SyntaxFactory.MemberAccessExpression(
                        SyntaxKind.SimpleMemberAccessExpression,
                        SyntaxFactory.IdentifierName("Console"),
                        SyntaxFactory.IdentifierName("WriteLine")
                    ),
                    SyntaxFactory.ArgumentList(
                        SyntaxFactory.SingletonSeparatedList(
                            SyntaxFactory.Argument(interpolatedString)
                        )
                    )
                )
            );
        }
    }

    /// <summary>
    /// Rewrites return statements inside a method body to inject an exit log statement just before returning.
    /// </summary>
    class ReturnInjector : CSharpSyntaxRewriter
    {
        private readonly string methodName;
        private readonly string fullClassPath;

        public ReturnInjector(string methodName, string fullClassPath)
        {
            this.methodName = methodName;
            this.fullClassPath = fullClassPath;
        }

        public override SyntaxNode VisitReturnStatement(ReturnStatementSyntax node)
        {
            // Create an interpolated string for the timestamp
            var interpolatedString = SyntaxFactory.InterpolatedStringExpression(
                SyntaxFactory.Token(SyntaxKind.InterpolatedStringStartToken),
                SyntaxFactory.List<InterpolatedStringContentSyntax>()
                    .Add(SyntaxFactory.InterpolatedStringText(
                        SyntaxFactory.Token(
                            SyntaxFactory.TriviaList(),
                            SyntaxKind.InterpolatedStringTextToken,
                            $"AXAL_EXIT {fullClassPath} {methodName} {{DateTime.Now.ToString(\"yyyy-MM-dd HH:mm:ss.ffffff\")}}",
                            $"AXAL_EXIT {fullClassPath} {methodName} {{DateTime.Now.ToString(\"yyyy-MM-dd HH:mm:ss.ffffff\")}}",
                            SyntaxFactory.TriviaList()
                        )
                    ))
            );
            
            var exitLog = SyntaxFactory.ExpressionStatement(
                SyntaxFactory.InvocationExpression(
                    SyntaxFactory.MemberAccessExpression(
                        SyntaxKind.SimpleMemberAccessExpression,
                        SyntaxFactory.IdentifierName("Console"),
                        SyntaxFactory.IdentifierName("WriteLine")
                    ),
                    SyntaxFactory.ArgumentList(
                        SyntaxFactory.SingletonSeparatedList(
                            SyntaxFactory.Argument(interpolatedString)
                        )
                    )
                )
            );

            // Wrap the exit log and the original return in a block.
            // This ensures that even if a return occurs in a conditional branch, the log is executed.
            var newReturn = SyntaxFactory.ReturnStatement(node.Expression);
            return SyntaxFactory.Block(exitLog, newReturn);
        }
    }
}